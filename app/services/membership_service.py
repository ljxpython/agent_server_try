from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.db.access import (
    create_or_update_membership,
    delete_membership,
    get_membership,
    get_user_by_external_subject,
    get_user_by_id,
    parse_uuid,
    upsert_user_from_subject,
)
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    remove_tenant_membership_fga,
    require_tenant_admin,
    resolve_tenant_or_404,
    sync_tenant_membership_fga,
)


async def add_membership_to_tenant(
    request: Request,
    tenant_ref: str,
    role: str,
    external_subject: str | None,
    user_id: str | None,
    email: str | None,
) -> dict[str, str]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)

    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        target_user = None
        target_uuid = parse_uuid(user_id or "") if user_id else None
        if target_uuid is not None:
            target_user = get_user_by_id(session, target_uuid)

        if target_user is None and external_subject:
            target_user = get_user_by_external_subject(session, external_subject)

        if target_user is None and external_subject:
            target_user = upsert_user_from_subject(
                session,
                external_subject=external_subject,
                email=email,
            )

        if target_user is None:
            raise HTTPException(status_code=404, detail="Target user not found")

        membership = create_or_update_membership(
            session,
            tenant_id=tenant.id,
            user_id=target_user.id,
            role=role,
        )

        user_subject = external_subject or target_user.external_subject
        await sync_tenant_membership_fga(
            request,
            tenant_id=str(tenant.id),
            user_subject=str(user_subject),
            role=role,
        )

        return {
            "tenant_id": str(membership.tenant_id),
            "user_id": str(membership.user_id),
            "role": membership.role,
        }


async def remove_membership_from_tenant(request: Request, tenant_ref: str, user_ref: str) -> dict[str, Any]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)

    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        target_user = None
        user_uuid = parse_uuid(user_ref)
        if user_uuid is not None:
            target_user = get_user_by_id(session, user_uuid)
        if target_user is None:
            target_user = get_user_by_external_subject(session, user_ref)
        if target_user is None:
            raise HTTPException(status_code=404, detail="Target user not found")

        membership = get_membership(session, tenant_id=tenant.id, user_id=target_user.id)
        if membership is None:
            return {
                "tenant_id": str(tenant.id),
                "user_id": str(target_user.id),
                "deleted": False,
            }

        delete_membership(session, membership)
        await remove_tenant_membership_fga(
            request,
            tenant_id=str(tenant.id),
            user_subject=target_user.external_subject,
        )
        return {
            "tenant_id": str(tenant.id),
            "user_id": str(target_user.id),
            "deleted": True,
        }
