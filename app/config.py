from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    langgraph_upstream_url: str
    langgraph_upstream_api_key: str | None
    proxy_timeout_seconds: float
    proxy_cors_allow_origins: list[str]
    proxy_upstream_retries: int
    proxy_log_level: str
    runtime_role_enforcement_enabled: bool
    platform_db_enabled: bool
    platform_db_auto_create: bool
    database_url: str | None
    require_tenant_context: bool
    keycloak_auth_enabled: bool
    keycloak_auth_required: bool
    keycloak_issuer: str | None
    keycloak_audience: str | None
    keycloak_jwks_url: str | None
    keycloak_jwks_cache_ttl_seconds: int
    openfga_enabled: bool
    openfga_authz_enabled: bool
    openfga_auto_bootstrap: bool
    openfga_url: str
    openfga_store_id: str | None
    openfga_model_id: str | None
    openfga_model_file: str
    logs_dir: str
    backend_log_file: str
    backend_log_max_bytes: int
    backend_log_backup_count: int


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        langgraph_upstream_url=os.getenv("LANGGRAPH_UPSTREAM_URL", "http://127.0.0.1:8123"),
        langgraph_upstream_api_key=os.getenv("LANGGRAPH_UPSTREAM_API_KEY") or None,
        proxy_timeout_seconds=float(os.getenv("PROXY_TIMEOUT_SECONDS", "300")),
        proxy_cors_allow_origins=os.getenv("PROXY_CORS_ALLOW_ORIGINS", "*").split(","),
        proxy_upstream_retries=max(0, int(os.getenv("PROXY_UPSTREAM_RETRIES", "1"))),
        proxy_log_level=os.getenv("PROXY_LOG_LEVEL", "INFO").upper(),
        runtime_role_enforcement_enabled=_as_bool(os.getenv("RUNTIME_ROLE_ENFORCEMENT_ENABLED", "false")),
        platform_db_enabled=_as_bool(os.getenv("PLATFORM_DB_ENABLED", "false")),
        platform_db_auto_create=_as_bool(os.getenv("PLATFORM_DB_AUTO_CREATE", "false")),
        database_url=os.getenv("DATABASE_URL") or None,
        require_tenant_context=_as_bool(os.getenv("REQUIRE_TENANT_CONTEXT", "false")),
        keycloak_auth_enabled=_as_bool(os.getenv("KEYCLOAK_AUTH_ENABLED", "false")),
        keycloak_auth_required=_as_bool(os.getenv("KEYCLOAK_AUTH_REQUIRED", "false")),
        keycloak_issuer=os.getenv("KEYCLOAK_ISSUER") or None,
        keycloak_audience=os.getenv("KEYCLOAK_AUDIENCE") or None,
        keycloak_jwks_url=os.getenv("KEYCLOAK_JWKS_URL") or None,
        keycloak_jwks_cache_ttl_seconds=max(30, int(os.getenv("KEYCLOAK_JWKS_CACHE_TTL_SECONDS", "300"))),
        openfga_enabled=_as_bool(os.getenv("OPENFGA_ENABLED", "false")),
        openfga_authz_enabled=_as_bool(os.getenv("OPENFGA_AUTHZ_ENABLED", "false")),
        openfga_auto_bootstrap=_as_bool(os.getenv("OPENFGA_AUTO_BOOTSTRAP", "false")),
        openfga_url=os.getenv("OPENFGA_URL", "http://127.0.0.1:18081"),
        openfga_store_id=os.getenv("OPENFGA_STORE_ID") or None,
        openfga_model_id=os.getenv("OPENFGA_MODEL_ID") or None,
        openfga_model_file=os.getenv("OPENFGA_MODEL_FILE", "config/openfga-models/v1.json"),
        logs_dir=os.getenv("LOGS_DIR", "logs"),
        backend_log_file=os.getenv("BACKEND_LOG_FILE", "backend.log"),
        backend_log_max_bytes=max(1024 * 1024, int(os.getenv("BACKEND_LOG_MAX_BYTES", str(10 * 1024 * 1024)))),
        backend_log_backup_count=max(1, int(os.getenv("BACKEND_LOG_BACKUP_COUNT", "5"))),
    )
