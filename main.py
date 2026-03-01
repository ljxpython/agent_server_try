from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from dotenv import load_dotenv

from app.api.platform import router as platform_router
from app.auth.keycloak import KeycloakSettings, KeycloakVerifier
from app.auth.openfga import OpenFgaClient, OpenFgaSettings
from app.config import Settings, load_settings
from app.db.access import create_audit_log, parse_uuid
from app.db.init_db import create_core_tables
from app.db.session import build_engine, build_session_factory, session_scope
from app.logging_setup import setup_backend_logging
from app.middleware.auth_context import register_auth_context_middleware
from app.middleware.tenant_context import register_tenant_context_middleware
from app.api.proxy.runtime_passthrough import passthrough_request


load_dotenv()
settings = load_settings()
setup_backend_logging(settings)

logger = logging.getLogger("proxy")


def _request_id(request: Request) -> str:
    incoming = request.headers.get("x-request-id")
    if incoming:
        return incoming
    return uuid.uuid4().hex


def _audit_plane(path: str) -> str:
    if path.startswith("/_platform/"):
        return "control_plane"
    if path.startswith("/_proxy/"):
        return "internal"
    return "runtime_proxy"


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    timeout = httpx.Timeout(
        connect=5.0,
        read=settings.proxy_timeout_seconds,
        write=settings.proxy_timeout_seconds,
        pool=5.0,
    )
    app.state.client = httpx.AsyncClient(timeout=timeout)
    logger.info(
        "startup_http_client_ready timeout_read=%s timeout_connect=%s",
        settings.proxy_timeout_seconds,
        5.0,
    )

    if settings.keycloak_auth_enabled:
        keycloak_settings = KeycloakSettings(
            enabled=settings.keycloak_auth_enabled,
            required=settings.keycloak_auth_required,
            issuer=settings.keycloak_issuer,
            audience=settings.keycloak_audience,
            jwks_url=settings.keycloak_jwks_url,
            cache_ttl_seconds=settings.keycloak_jwks_cache_ttl_seconds,
        )
        app.state.keycloak_verifier = KeycloakVerifier(keycloak_settings)
        logger.info(
            "startup_keycloak_enabled issuer=%s audience=%s jwks_url=%s",
            settings.keycloak_issuer,
            settings.keycloak_audience,
            settings.keycloak_jwks_url or "<issuer>/protocol/openid-connect/certs",
        )
    else:
        app.state.keycloak_verifier = None
        logger.info("startup_keycloak_disabled")

    if settings.openfga_enabled:
        app.state.openfga_client = OpenFgaClient(
            OpenFgaSettings(
                enabled=settings.openfga_enabled,
                authz_enabled=settings.openfga_authz_enabled,
                auto_bootstrap=settings.openfga_auto_bootstrap,
                base_url=settings.openfga_url,
                store_id=settings.openfga_store_id,
                model_id=settings.openfga_model_id,
                model_file=settings.openfga_model_file,
            )
        )
        await app.state.openfga_client.ensure_ready()
        logger.info(
            "startup_openfga_enabled url=%s store_id=%s model_id=%s",
            settings.openfga_url,
            settings.openfga_store_id,
            settings.openfga_model_id,
        )
    else:
        app.state.openfga_client = None
        logger.info("startup_openfga_disabled")

    if settings.platform_db_enabled:
        app.state.db_engine = build_engine(settings)
        app.state.db_session_factory = build_session_factory(app.state.db_engine)
        if settings.platform_db_auto_create:
            create_core_tables(app.state.db_engine)
        logger.info("startup_platform_db_enabled auto_create=%s", settings.platform_db_auto_create)
    else:
        logger.info("startup_platform_db_disabled")

    try:
        yield
    finally:
        if settings.openfga_enabled and app.state.openfga_client is not None:
            await app.state.openfga_client.aclose()
        if settings.platform_db_enabled:
            app.state.db_engine.dispose()
        await app.state.client.aclose()
        logger.info("shutdown_complete")


app = FastAPI(
    title="LangGraph Transparent Proxy",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)
app.include_router(platform_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.proxy_cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_tenant_context_middleware(app, settings)
register_auth_context_middleware(app, settings)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = _request_id(request)
    request.state.request_id = request_id
    logger.info(
        "request_started request_id=%s method=%s path=%s query=%s",
        request_id,
        request.method,
        request.url.path,
        request.url.query,
    )

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        if settings.platform_db_enabled:
            session_factory = getattr(request.app.state, "db_session_factory", None)
            if session_factory is not None:
                try:
                    with session_scope(session_factory) as session:
                        create_audit_log(
                            session=session,
                            request_id=request_id,
                            plane=_audit_plane(request.url.path),
                            method=request.method,
                            path=request.url.path,
                            query=request.url.query,
                            status_code=500,
                            duration_ms=int(elapsed_ms),
                            tenant_id=parse_uuid(getattr(request.state, "tenant_id", "") or ""),
                            user_id=parse_uuid(getattr(request.state, "user_id", "") or ""),
                            user_subject=getattr(request.state, "user_subject", None),
                            client_ip=request.client.host if request.client else None,
                            user_agent=request.headers.get("user-agent"),
                            response_size=None,
                            metadata_json={
                                "route_kind": _audit_plane(request.url.path),
                                "error": True,
                            },
                        )
                except Exception:
                    logger.exception("audit_write_failed request_id=%s", request_id)
        raise

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )

    if settings.platform_db_enabled:
        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is not None:
            try:
                with session_scope(session_factory) as session:
                    create_audit_log(
                        session=session,
                        request_id=request_id,
                        plane=_audit_plane(request.url.path),
                        method=request.method,
                        path=request.url.path,
                        query=request.url.query,
                        status_code=response.status_code,
                        duration_ms=int(elapsed_ms),
                        tenant_id=parse_uuid(getattr(request.state, "tenant_id", "") or ""),
                        user_id=parse_uuid(getattr(request.state, "user_id", "") or ""),
                        user_subject=getattr(request.state, "user_subject", None),
                        client_ip=request.client.host if request.client else None,
                        user_agent=request.headers.get("user-agent"),
                        response_size=_to_int(response.headers.get("content-length")),
                        metadata_json={
                            "route_kind": _audit_plane(request.url.path),
                            "has_tenant_header": bool(request.headers.get("x-tenant-id")),
                        },
                    )
            except Exception:
                logger.exception("audit_write_failed request_id=%s", request_id)
    return response


@app.get("/_proxy/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def passthrough(request: Request, full_path: str) -> Response:
    return await passthrough_request(request=request, full_path=full_path, settings=settings, logger=logger)
