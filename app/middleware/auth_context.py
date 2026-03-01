from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.keycloak import KeycloakVerifier, extract_bearer_token, is_invalid_token_error
from app.config import Settings
from app.db.access import upsert_user_from_subject
from app.db.session import session_scope


logger = logging.getLogger("proxy.auth")


def register_auth_context_middleware(
    app: FastAPI,
    settings: Settings,
) -> None:
    docs_paths = {"/docs", "/openapi.json", "/redoc"}

    @app.middleware("http")
    async def auth_context_middleware(request: Request, call_next):
        if (
            request.url.path == "/_proxy/health"
            or request.method.upper() == "OPTIONS"
            or (settings.api_docs_enabled and request.url.path in docs_paths)
        ):
            return await call_next(request)

        request.state.auth_claims = None
        request.state.user_subject = None

        if settings.dev_auth_bypass_enabled:
            is_fixed_mode = settings.dev_auth_bypass_mode == "fixed"
            subject = settings.dev_auth_bypass_subject if is_fixed_mode else "dev-anonymous"
            email = settings.dev_auth_bypass_email if is_fixed_mode else None
            request.state.auth_claims = {
                "sub": subject,
                "email": email,
                "dev_auth_bypass": True,
                "dev_auth_mode": settings.dev_auth_bypass_mode,
            }
            request.state.user_subject = subject

            if settings.platform_db_enabled:
                session_factory = getattr(request.app.state, "db_session_factory", None)
                if session_factory is None:
                    logger.error(
                        "auth_db_misconfigured request_id=%s path=%s",
                        getattr(request.state, "request_id", "-"),
                        request.url.path,
                    )
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
                        email=email,
                    )
                    request.state.user_id = str(user.id)
            else:
                request.state.user_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"dev-auth-bypass:{subject}"))

            response = await call_next(request)
            response.headers["x-user-subject"] = str(subject)
            if getattr(request.state, "user_id", None):
                response.headers["x-user-id"] = str(request.state.user_id)
            response.headers["x-dev-auth-bypass"] = "true"
            return response

        if not settings.keycloak_auth_enabled:
            return await call_next(request)

        token = extract_bearer_token(request.headers.get("authorization"))
        token_source = "authorization"
        if not token:
            token = request.headers.get("x-api-key")
            token_source = "x-api-key"

        logger.debug(
            "auth_check_started request_id=%s path=%s method=%s token_source=%s has_token=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
            request.method,
            token_source,
            bool(token),
        )

        if not token:
            if settings.keycloak_auth_required:
                logger.warning(
                    "auth_missing_token request_id=%s path=%s method=%s",
                    getattr(request.state, "request_id", "-"),
                    request.url.path,
                    request.method,
                )
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
            logger.error(
                "auth_verifier_missing request_id=%s path=%s",
                getattr(request.state, "request_id", "-"),
                request.url.path,
            )
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
                logger.warning(
                    "auth_invalid_token request_id=%s path=%s method=%s token_source=%s error=%s",
                    getattr(request.state, "request_id", "-"),
                    request.url.path,
                    request.method,
                    token_source,
                    exc,
                )
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
            logger.error(
                "auth_provider_unavailable request_id=%s path=%s method=%s error=%s",
                getattr(request.state, "request_id", "-"),
                request.url.path,
                request.method,
                exc,
            )
            return JSONResponse(
                status_code=502,
                content={
                    "error": "auth_provider_unavailable",
                    "message": f"Failed to validate token with Keycloak JWKS: {exc}",
                },
            )

        subject = claims.get("sub")
        logger.info(
            "auth_verified request_id=%s path=%s subject=%s email=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
            subject,
            claims.get("email"),
        )
        request.state.auth_claims = claims
        request.state.user_subject = subject

        if settings.platform_db_enabled and subject:
            session_factory = getattr(request.app.state, "db_session_factory", None)
            if session_factory is None:
                logger.error(
                    "auth_db_misconfigured request_id=%s path=%s",
                    getattr(request.state, "request_id", "-"),
                    request.url.path,
                )
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
                logger.debug(
                    "auth_user_upserted request_id=%s subject=%s user_id=%s",
                    getattr(request.state, "request_id", "-"),
                    subject,
                    request.state.user_id,
                )

        response = await call_next(request)
        if subject:
            response.headers["x-user-subject"] = str(subject)
        if getattr(request.state, "user_id", None):
            response.headers["x-user-id"] = str(request.state.user_id)
        return response
