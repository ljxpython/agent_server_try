from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import FastAPI

from app.auth.keycloak import KeycloakSettings, KeycloakVerifier
from app.auth.openfga import OpenFgaClient, OpenFgaSettings
from app.config import Settings
from app.db.init_db import create_core_tables
from app.db.session import build_engine, build_session_factory


logger = logging.getLogger("proxy")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings

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

    if settings.dev_auth_bypass_enabled:
        logger.warning(
            "startup_dev_auth_bypass_enabled mode=%s role=%s membership_bypass=%s",
            settings.dev_auth_bypass_mode,
            settings.dev_auth_bypass_role,
            settings.dev_auth_bypass_membership_enabled,
        )

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
