from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError

from app.db.access import create_or_update_membership, create_tenant, list_tenants_for_user
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    logger,
    slugify,
    sync_tenant_membership_fga,
)


async def list_my_tenants(
    request: Request,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, str]], int]:
    user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        tenants, total = list_tenants_for_user(
            session,
            user_id=user_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return (
            [
                {
                    "id": str(t.id),
                    "name": t.name,
                    "slug": t.slug,
                    "status": t.status,
                }
                for t in tenants
            ],
            total,
        )


async def create_tenant_for_current_user(
    request: Request,
    name: str,
    slug: str | None,
) -> dict[str, str]:
    user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)
    resolved_slug = slug or slugify(name)

    with session_scope(session_factory) as session:
        try:
            tenant = create_tenant(session, name=name, slug=resolved_slug)
            create_or_update_membership(
                session,
                tenant_id=tenant.id,
                user_id=user_id,
                role="owner",
            )
        except IntegrityError as exc:
            logger.warning(
                "platform_create_tenant_conflict request_id=%s slug=%s error=%s",
                getattr(request.state, "request_id", "-"),
                resolved_slug,
                exc,
            )
            raise HTTPException(status_code=409, detail=f"Tenant slug already exists: {resolved_slug}") from exc

        if getattr(request.state, "user_subject", None):
            await sync_tenant_membership_fga(
                request,
                tenant_id=str(tenant.id),
                user_subject=str(request.state.user_subject),
                role="owner",
            )

        return {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
        }
