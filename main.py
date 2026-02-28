from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from dotenv import load_dotenv

from app.api.platform import router as platform_router
from app.auth.keycloak import KeycloakSettings, KeycloakVerifier
from app.auth.openfga import OpenFgaClient, OpenFgaSettings, fga_agent, fga_tenant, fga_user
from app.config import Settings, load_settings
from app.db.access import create_audit_log, get_agent_with_project, parse_uuid
from app.db.init_db import create_core_tables
from app.db.session import build_engine, build_session_factory, session_scope
from app.middleware.auth_context import register_auth_context_middleware
from app.middleware.tenant_context import register_tenant_context_middleware


load_dotenv()
settings = load_settings()

logger = logging.getLogger("proxy")
logging.basicConfig(
    level=settings.proxy_log_level,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _strip_request_headers(headers: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in HOP_BY_HOP_HEADERS or lower_key in {"host", "content-length"}:
            continue
        cleaned[key] = value
    return cleaned


def _strip_response_headers(headers: httpx.Headers) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in HOP_BY_HOP_HEADERS or lower_key == "content-length":
            continue
        cleaned[key] = value
    return cleaned


def _upstream_url(base_url: str, path: str, query: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path.lstrip("/")
    url = f"{normalized_base}/{normalized_path}"
    if query:
        return f"{url}?{query}"
    return url


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


def _runtime_write_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


def _cors_json_error(request: Request, status_code: int, content: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Vary": "Origin",
        },
    )


def _enforce_tenant_write_policy(request: Request, settings: Settings) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    if not settings.runtime_role_enforcement_enabled:
        return None
    if not getattr(request.state, "tenant_id", None):
        return None
    role = getattr(request.state, "membership_role", None)
    if role == "member" and _runtime_write_method(request.method):
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "Member role cannot perform runtime write operations",
                "request_id": request.state.request_id,
            },
        )
    return None


def _enforce_agent_mapping(request: Request) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    tenant_id = getattr(request.state, "tenant_id", None)
    agent_header = request.headers.get("x-agent-id")
    if not agent_header:
        return None

    if not tenant_id:
        return _cors_json_error(
            request,
            400,
            {
                "error": "agent_context_invalid",
                "message": "x-agent-id requires x-tenant-id context",
                "request_id": request.state.request_id,
            },
        )

    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        return _cors_json_error(
            request,
            503,
            {
                "error": "db_misconfigured",
                "message": "Database is required for agent mapping checks",
                "request_id": request.state.request_id,
            },
        )

    agent_uuid = parse_uuid(agent_header)
    if agent_uuid is None:
        return _cors_json_error(
            request,
            400,
            {
                "error": "agent_context_invalid",
                "message": "Invalid x-agent-id",
                "request_id": request.state.request_id,
            },
        )

    with session_scope(session_factory) as session:
        row = get_agent_with_project(session, agent_uuid)
        if row is None:
            return _cors_json_error(
                request,
                404,
                {
                    "error": "agent_not_found",
                    "message": "Agent not found",
                    "request_id": request.state.request_id,
                },
            )
        agent, project = row
        if str(project.tenant_id) != str(tenant_id):
            return _cors_json_error(
                request,
                403,
                {
                    "error": "runtime_policy_denied",
                    "message": "Agent does not belong to tenant",
                    "request_id": request.state.request_id,
                },
            )
        request.state.agent_id = str(agent.id)
    return None


async def _enforce_openfga_runtime_policy(request: Request, settings: Settings) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    if not settings.openfga_authz_enabled:
        return None
    if not getattr(request.state, "tenant_id", None):
        return None

    openfga_client = getattr(request.app.state, "openfga_client", None)
    user_subject = getattr(request.state, "user_subject", None)
    if openfga_client is None or not user_subject:
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "OpenFGA authorization context is incomplete",
                "request_id": request.state.request_id,
            },
        )

    relation = "can_write" if _runtime_write_method(request.method) else "can_read"

    tenant_allowed = await openfga_client.check(
        user=fga_user(str(user_subject)),
        relation=relation,
        obj=fga_tenant(str(request.state.tenant_id)),
    )
    if not tenant_allowed:
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "OpenFGA denied access to tenant runtime",
                "request_id": request.state.request_id,
            },
        )

    agent_id = getattr(request.state, "agent_id", None)
    if agent_id:
        agent_allowed = await openfga_client.check(
            user=fga_user(str(user_subject)),
            relation=relation,
            obj=fga_agent(str(agent_id)),
        )
        if not agent_allowed:
            return _cors_json_error(
                request,
                403,
                {
                    "error": "runtime_policy_denied",
                    "message": "OpenFGA denied access to agent runtime",
                    "request_id": request.state.request_id,
                },
            )

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
    else:
        app.state.keycloak_verifier = None

    if settings.openfga_enabled:
        app.state.openfga_client = OpenFgaClient(
            OpenFgaSettings(
                enabled=settings.openfga_enabled,
                authz_enabled=settings.openfga_authz_enabled,
                auto_bootstrap=settings.openfga_auto_bootstrap,
                base_url=settings.openfga_url,
                store_id=settings.openfga_store_id,
                model_id=settings.openfga_model_id,
            )
        )
        await app.state.openfga_client.ensure_ready()
    else:
        app.state.openfga_client = None

    if settings.platform_db_enabled:
        app.state.db_engine = build_engine(settings)
        app.state.db_session_factory = build_session_factory(app.state.db_engine)
        if settings.platform_db_auto_create:
            create_core_tables(app.state.db_engine)

    try:
        yield
    finally:
        if settings.openfga_enabled and app.state.openfga_client is not None:
            await app.state.openfga_client.aclose()
        if settings.platform_db_enabled:
            app.state.db_engine.dispose()
        await app.state.client.aclose()


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
    upstream_base_url = settings.langgraph_upstream_url
    upstream_api_key = settings.langgraph_upstream_api_key
    upstream_url = _upstream_url(upstream_base_url, full_path, request.url.query)

    violation = _enforce_tenant_write_policy(request, settings)
    if violation is not None:
        return violation

    violation = _enforce_agent_mapping(request)
    if violation is not None:
        return violation

    violation = await _enforce_openfga_runtime_policy(request, settings)
    if violation is not None:
        return violation

    headers = _strip_request_headers(dict(request.headers))
    headers["x-request-id"] = request.state.request_id
    if upstream_api_key:
        headers["x-api-key"] = upstream_api_key

    body = await request.body()

    retries = settings.proxy_upstream_retries
    attempt = 0
    upstream_response = None

    while attempt <= retries:
        try:
            upstream_request = app.state.client.build_request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
            )
            upstream_response = await app.state.client.send(upstream_request, stream=True)
            break
        except httpx.TimeoutException as exc:
            if attempt < retries:
                attempt += 1
                continue
            return _cors_json_error(
                request,
                504,
                {
                    "error": "gateway_timeout",
                    "message": f"Upstream timeout: {exc}",
                    "request_id": request.state.request_id,
                },
            )
        except httpx.HTTPError as exc:
            if attempt < retries:
                attempt += 1
                continue
            return _cors_json_error(
                request,
                502,
                {
                    "error": "bad_gateway",
                    "message": f"Failed to reach upstream: {exc}",
                    "request_id": request.state.request_id,
                },
            )

    if upstream_response is None:
        return _cors_json_error(
            request,
            502,
            {
                "error": "bad_gateway",
                "message": "Failed to reach upstream",
                "request_id": request.state.request_id,
            },
        )

    response_headers = _strip_response_headers(upstream_response.headers)

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream_response.aiter_raw():
                if chunk:
                    yield chunk
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
