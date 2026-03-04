from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.db.access import get_user_by_id, parse_uuid
from app.db.session import session_scope
from app.security.token import InvalidTokenError, decode_access_token


logger = logging.getLogger("proxy.auth")


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def register_auth_context_middleware(app: FastAPI, settings: Settings) -> None:
    docs_paths = {"/docs", "/openapi.json", "/redoc"}
    public_paths = {"/_proxy/health", "/_management/auth/login", "/_management/auth/refresh"}

    @app.middleware("http")
    async def auth_context_middleware(request: Request, call_next):
        if (
            request.url.path in public_paths
            or request.method.upper() == "OPTIONS"
            or (settings.api_docs_enabled and request.url.path in docs_paths)
        ):
            return await call_next(request)

        request.state.user_id = None
        request.state.username = None
        request.state.auth_claims = None

        token = _extract_bearer_token(request.headers.get("authorization"))
        if not token:
            if settings.auth_required:
                return JSONResponse(
                    status_code=401,
                    content={"error": "unauthorized", "message": "Missing bearer token"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await call_next(request)

        try:
            payload = decode_access_token(token, settings)
        except InvalidTokenError as exc:
            logger.warning(
                "auth_invalid_token request_id=%s path=%s error=%s",
                getattr(request.state, "request_id", "-"),
                request.url.path,
                exc,
            )
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "message": "Token validation failed"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = payload.get("sub")
        username = payload.get("username")
        if not user_id or not username:
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_token", "message": "Token payload is incomplete"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.user_id = str(user_id)
        request.state.username = str(username)
        request.state.user_subject = str(username)
        request.state.auth_claims = payload

        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is not None:
            user_uuid = parse_uuid(str(user_id))
            if user_uuid is None:
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_token", "message": "Token subject is invalid"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
            with session_scope(session_factory) as session:
                user = get_user_by_id(session, user_uuid)
                if user is None or user.status != "active":
                    return JSONResponse(
                        status_code=403,
                        content={"error": "user_disabled", "message": "User is disabled"},
                    )

        response = await call_next(request)
        response.headers["x-user-id"] = str(user_id)
        response.headers["x-username"] = str(username)
        return response
