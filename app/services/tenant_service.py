from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.exc import IntegrityError

from app.db.access import (
    create_or_update_membership,
    create_tenant,
    delete_tenant,
    list_agents_for_tenant,
    list_memberships_for_tenant,
    list_projects_for_tenant,
    list_tenants_for_user,
)
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    logger,
    remove_agent_fga,
    remove_project_fga,
    remove_tenant_membership_fga,
    require_tenant_admin,
    resolve_tenant_or_404,
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


async def delete_tenant_by_ref(request: Request, tenant_ref: str) -> dict[str, str | bool]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)

    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(
            session,
            tenant_id=tenant.id,
            acting_user_id=acting_user_id,
            request=request,
        )

        membership_rows, _ = list_memberships_for_tenant(session, tenant_id=tenant.id, limit=5000, offset=0)
        projects, _ = list_projects_for_tenant(session, tenant_id=tenant.id, limit=5000, offset=0)
        agents = list_agents_for_tenant(session, tenant_id=tenant.id)

        for membership in membership_rows:
            await remove_tenant_membership_fga(
                request,
                tenant_id=str(tenant.id),
                user_subject=membership.user.external_subject,
            )

        for project in projects:
            for agent in agents:
                if agent.project_id == project.id:
                    await remove_agent_fga(request, agent_id=str(agent.id), project_id=str(project.id))
            await remove_project_fga(request, project_id=str(project.id), tenant_id=str(tenant.id))

        tenant_id = str(tenant.id)
        delete_tenant(session, tenant)
        return {
            "deleted": True,
            "tenant_id": tenant_id,
        }
