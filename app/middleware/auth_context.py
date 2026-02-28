from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.keycloak import KeycloakVerifier, extract_bearer_token, is_invalid_token_error
from app.config import Settings
from app.db.access import upsert_user_from_subject
from app.db.session import session_scope


def register_auth_context_middleware(
    app: FastAPI,
    settings: Settings,
) -> None:
    @app.middleware("http")
    async def auth_context_middleware(request: Request, call_next):
        if request.url.path == "/_proxy/health" or request.method.upper() == "OPTIONS":
            return await call_next(request)

        request.state.auth_claims = None
        request.state.user_subject = None

        if not settings.keycloak_auth_enabled:
            return await call_next(request)

        token = extract_bearer_token(request.headers.get("authorization"))
        if not token:
            token = request.headers.get("x-api-key")
        if not token:
            if settings.keycloak_auth_required:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "unauthorized",
                        "message": "Missing bearer token",
                    },
                    headers={
                        "WWW-Authenticate": "Bearer",
                        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                        "Vary": "Origin",
                    },
                )
            return await call_next(request)

        verifier: KeycloakVerifier | None = getattr(request.app.state, "keycloak_verifier", None)
        if verifier is None:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "auth_misconfigured",
                    "message": "Keycloak verifier is not initialized",
                },
            )

        try:
            claims = verifier.verify_token(token)
        except Exception as exc:
            if is_invalid_token_error(exc):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": "invalid_token",
                        "message": "Bearer token validation failed",
                    },
                    headers={
                        "WWW-Authenticate": "Bearer",
                        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                        "Vary": "Origin",
                    },
                )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "auth_provider_unavailable",
                    "message": f"Failed to validate token with Keycloak JWKS: {exc}",
                },
            )

        subject = claims.get("sub")
        request.state.auth_claims = claims
        request.state.user_subject = subject

        if settings.platform_db_enabled and subject:
            session_factory = getattr(request.app.state, "db_session_factory", None)
            if session_factory is None:
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "db_misconfigured",
                        "message": "Database session factory is not initialized",
                    },
                )

            with session_scope(session_factory) as session:
                user = upsert_user_from_subject(
                    session,
                    external_subject=str(subject),
                    email=claims.get("email"),
                )
                request.state.user_id = str(user.id)

        response = await call_next(request)
        if subject:
            response.headers["x-user-subject"] = str(subject)
        if getattr(request.state, "user_id", None):
            response.headers["x-user-id"] = str(request.state.user_id)
        return response
