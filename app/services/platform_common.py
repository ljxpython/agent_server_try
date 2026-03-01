from __future__ import annotations

import logging
import re
import uuid
from types import SimpleNamespace

from fastapi import HTTPException, Request

from app.auth.openfga import fga_agent, fga_project, fga_tenant, fga_user
from app.db.access import get_membership, parse_uuid, resolve_tenant


logger = logging.getLogger("proxy.platform")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or uuid.uuid4().hex[:12]


def db_session_factory_from_request(request: Request):
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        logger.error(
            "platform_db_unavailable request_id=%s path=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
        )
        raise HTTPException(status_code=503, detail="Database is not enabled")
    return session_factory


def _settings_from_request(request: Request):
    return getattr(request.app.state, "settings", None)


def _dev_auth_bypass_enabled(request: Request) -> bool:
    settings = _settings_from_request(request)
    return bool(getattr(settings, "dev_auth_bypass_enabled", False))


def _dev_auth_bypass_membership_enabled(request: Request) -> bool:
    settings = _settings_from_request(request)
    return bool(getattr(settings, "dev_auth_bypass_enabled", False)) and bool(
        getattr(settings, "dev_auth_bypass_membership_enabled", False)
    )


def _dev_auth_bypass_role(request: Request) -> str:
    settings = _settings_from_request(request)
    return str(getattr(settings, "dev_auth_bypass_role", "owner"))


def current_user_id_from_request(request: Request) -> uuid.UUID:
    user_id = getattr(request.state, "user_id", None)
    parsed = parse_uuid(str(user_id) if user_id else "")
    if parsed is None:
        if _dev_auth_bypass_enabled(request):
            subject = str(getattr(request.state, "user_subject", "dev-anonymous"))
            return uuid.uuid5(uuid.NAMESPACE_URL, f"dev-auth-bypass:{subject}")
        logger.warning(
            "platform_user_missing request_id=%s path=%s",
            getattr(request.state, "request_id", "-"),
            request.url.path,
        )
        raise HTTPException(status_code=401, detail="Authenticated user is required")
    return parsed


def openfga_client_from_request(request: Request):
    return getattr(request.app.state, "openfga_client", None)


async def sync_tenant_membership_fga(request: Request, tenant_id: str, user_subject: str, role: str) -> None:
    client = openfga_client_from_request(request)
    if client is None:
        return
    logger.debug(
        "platform_fga_sync_membership request_id=%s tenant_id=%s user_subject=%s role=%s",
        getattr(request.state, "request_id", "-"),
        tenant_id,
        user_subject,
        role,
    )

    user = fga_user(user_subject)
    tenant = fga_tenant(tenant_id)
    role_relations = ["owner", "admin", "member"]
    await client.delete_tuples([
        {"user": user, "relation": rel, "object": tenant} for rel in role_relations
    ])
    await client.write_tuple(user=user, relation=role, obj=tenant)


async def remove_tenant_membership_fga(request: Request, tenant_id: str, user_subject: str) -> None:
    client = openfga_client_from_request(request)
    if client is None:
        return
    logger.debug(
        "platform_fga_remove_membership request_id=%s tenant_id=%s user_subject=%s",
        getattr(request.state, "request_id", "-"),
        tenant_id,
        user_subject,
    )
    user = fga_user(user_subject)
    tenant = fga_tenant(tenant_id)
    await client.delete_tuples(
        [
            {"user": user, "relation": "owner", "object": tenant},
            {"user": user, "relation": "admin", "object": tenant},
            {"user": user, "relation": "member", "object": tenant},
        ]
    )


async def remove_project_fga(request: Request, project_id: str, tenant_id: str) -> None:
    client = openfga_client_from_request(request)
    if client is None:
        return
    logger.debug(
        "platform_fga_remove_project request_id=%s project_id=%s tenant_id=%s",
        getattr(request.state, "request_id", "-"),
        project_id,
        tenant_id,
    )
    await client.delete_tuple(
        user=fga_tenant(tenant_id),
        relation="tenant",
        obj=fga_project(project_id),
    )


async def remove_agent_fga(request: Request, agent_id: str, project_id: str) -> None:
    client = openfga_client_from_request(request)
    if client is None:
        return
    logger.debug(
        "platform_fga_remove_agent request_id=%s agent_id=%s project_id=%s",
        getattr(request.state, "request_id", "-"),
        agent_id,
        project_id,
    )
    await client.delete_tuple(
        user=fga_project(project_id),
        relation="project",
        obj=fga_agent(agent_id),
    )


def resolve_tenant_or_404(session, tenant_ref: str):
    tenant = resolve_tenant(session, tenant_ref)
    if tenant is None:
        logger.warning("platform_tenant_not_found tenant_ref=%s", tenant_ref)
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def require_tenant_membership(
    session,
    tenant_id: uuid.UUID,
    acting_user_id: uuid.UUID,
    request: Request | None = None,
):
    if request is not None and _dev_auth_bypass_membership_enabled(request):
        role = _dev_auth_bypass_role(request)
        logger.warning(
            "platform_membership_bypassed tenant_id=%s user_id=%s role=%s",
            tenant_id,
            acting_user_id,
            role,
        )
        return SimpleNamespace(role=role)

    membership = get_membership(session, tenant_id=tenant_id, user_id=acting_user_id)
    if membership is None:
        logger.warning(
            "platform_membership_required tenant_id=%s user_id=%s",
            tenant_id,
            acting_user_id,
        )
        raise HTTPException(status_code=403, detail="Tenant membership required")
    return membership


def require_tenant_admin(
    session,
    tenant_id: uuid.UUID,
    acting_user_id: uuid.UUID,
    request: Request | None = None,
):
    membership = require_tenant_membership(session, tenant_id, acting_user_id, request=request)
    if membership.role not in {"owner", "admin"}:
        logger.warning(
            "platform_admin_required tenant_id=%s user_id=%s role=%s",
            tenant_id,
            acting_user_id,
            membership.role,
        )
        raise HTTPException(status_code=403, detail="Only owner/admin can perform this action")
    return membership
