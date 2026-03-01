from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings
from app.db.access import get_membership, get_user_by_external_subject, parse_uuid, resolve_tenant, upsert_user_from_subject
from app.db.models import User
from app.db.session import session_scope


logger = logging.getLogger("proxy.tenant")


def register_tenant_context_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def tenant_context_middleware(request: Request, call_next):
        if request.url.path == "/_proxy/health" or request.method.upper() == "OPTIONS":
            return await call_next(request)

        tenant_id = request.headers.get("x-tenant-id")
        user_id = request.headers.get("x-user-id")
        user_subject = getattr(request.state, "user_subject", None)
        auth_claims = getattr(request.state, "auth_claims", None) or {}

        logger.debug(
            "tenant_context_started request_id=%s path=%s method=%s tenant_header=%s user_id_header=%s user_subject=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
            request.method,
            tenant_id,
            user_id,
            user_subject,
        )

        if not user_id and user_subject:
            user_id = str(user_subject)

        if settings.require_tenant_context and not tenant_id:
            logger.warning(
                "tenant_context_required_missing request_id=%s path=%s",
                getattr(request.state, "request_id", "-"),
                request.url.path,
            )
            return JSONResponse(
                status_code=400,
                content={
                    "error": "tenant_context_required",
                    "message": "Missing required header: x-tenant-id",
                },
                headers={
                    "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                    "Vary": "Origin",
                },
            )

        resolved_tenant_id = tenant_id
        membership_role = None

        if settings.platform_db_enabled:
            session_factory = getattr(request.app.state, "db_session_factory", None)
            if session_factory is None:
                logger.error(
                    "tenant_db_misconfigured request_id=%s path=%s",
                    getattr(request.state, "request_id", "-"),
                    request.url.path,
                )
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": "db_misconfigured",
                        "message": "Database session factory is not initialized",
                    },
                    headers={
                        "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                        "Vary": "Origin",
                    },
                )

            with session_scope(session_factory) as session:
                user: User | None = None
                internal_user_id = parse_uuid(str(getattr(request.state, "user_id", "") or ""))
                if internal_user_id:
                    user = session.get(User, internal_user_id)

                if user is None and user_subject:
                    user = upsert_user_from_subject(
                        session,
                        external_subject=str(user_subject),
                        email=auth_claims.get("email"),
                    )
                elif user is None and user_id:
                    user = get_user_by_external_subject(session, str(user_id))

                if tenant_id:
                    tenant = resolve_tenant(session, tenant_id)
                    if tenant is None:
                        logger.warning(
                            "tenant_resolve_denied request_id=%s tenant_ref=%s",
                            getattr(request.state, "request_id", "-"),
                            tenant_id,
                        )
                        return JSONResponse(
                            status_code=403,
                            content={
                                "error": "tenant_access_denied",
                                "message": "Tenant access denied",
                            },
                            headers={
                                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                                "Vary": "Origin",
                            },
                        )
                    resolved_tenant_id = str(tenant.id)

                    if user is None:
                        logger.warning(
                            "tenant_access_user_missing request_id=%s tenant_id=%s",
                            getattr(request.state, "request_id", "-"),
                            resolved_tenant_id,
                        )
                        return JSONResponse(
                            status_code=401,
                            content={
                                "error": "unauthorized",
                                "message": "User identity is required for tenant access",
                            },
                            headers={
                                "WWW-Authenticate": "Bearer",
                                "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                                "Vary": "Origin",
                            },
                        )

                    if settings.dev_auth_bypass_enabled and settings.dev_auth_bypass_membership_enabled:
                        membership_role = settings.dev_auth_bypass_role
                        logger.warning(
                            "tenant_membership_bypassed request_id=%s tenant_id=%s user_id=%s role=%s",
                            getattr(request.state, "request_id", "-"),
                            resolved_tenant_id,
                            user.id,
                            membership_role,
                        )
                    else:
                        membership = get_membership(session, tenant.id, user.id)
                        if membership is None:
                            logger.warning(
                                "tenant_membership_missing request_id=%s tenant_id=%s user_id=%s",
                                getattr(request.state, "request_id", "-"),
                                resolved_tenant_id,
                                user.id,
                            )
                            return JSONResponse(
                                status_code=403,
                                content={
                                    "error": "tenant_access_denied",
                                    "message": "Tenant membership not found",
                                },
                                headers={
                                    "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
                                    "Vary": "Origin",
                                },
                            )
                        membership_role = membership.role
                        logger.info(
                            "tenant_membership_ok request_id=%s tenant_id=%s user_id=%s role=%s",
                            getattr(request.state, "request_id", "-"),
                            resolved_tenant_id,
                            user.id,
                            membership_role,
                        )

                if user is not None:
                    user_id = str(user.id)

        request.state.tenant_id = resolved_tenant_id
        request.state.user_id = user_id
        request.state.membership_role = membership_role

        logger.debug(
            "tenant_context_resolved request_id=%s tenant_id=%s user_id=%s role=%s",
            getattr(request.state, "request_id", "-"),
            resolved_tenant_id,
            user_id,
            membership_role,
        )

        response = await call_next(request)
        if resolved_tenant_id:
            response.headers["x-tenant-id"] = resolved_tenant_id
        if user_id:
            response.headers["x-user-id"] = user_id
        if membership_role:
            response.headers["x-membership-role"] = membership_role
        return response
