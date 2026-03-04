from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request

from app.config import Settings
from app.db.access import create_audit_log, parse_uuid
from app.db.session import session_scope


logger = logging.getLogger("proxy")


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


def _duration_ms(request: Request, fallback_started_at: float) -> float:
    started_at = getattr(request.state, "request_started_at", fallback_started_at)
    return round((time.perf_counter() - started_at) * 1000, 2)


def register_audit_log_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = _duration_ms(request, started)
            if settings.platform_db_enabled:
                session_factory = getattr(request.app.state, "db_session_factory", None)
                if session_factory is not None:
                    try:
                        with session_scope(session_factory) as session:
                            create_audit_log(
                                session=session,
                                request_id=getattr(request.state, "request_id", "-"),
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
                        logger.exception("audit_write_failed request_id=%s", getattr(request.state, "request_id", "-"))
            raise

        elapsed_ms = _duration_ms(request, started)
        if settings.platform_db_enabled:
            session_factory = getattr(request.app.state, "db_session_factory", None)
            if session_factory is not None:
                try:
                    with session_scope(session_factory) as session:
                        create_audit_log(
                            session=session,
                            request_id=getattr(request.state, "request_id", "-"),
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
                    logger.exception("audit_write_failed request_id=%s", getattr(request.state, "request_id", "-"))
        return response
