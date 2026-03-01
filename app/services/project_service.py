from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.auth.openfga import fga_project, fga_tenant
from app.db.access import (
    create_project,
    delete_project,
    get_project,
    list_agents_for_tenant,
    list_projects_for_tenant,
    parse_uuid,
)
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    openfga_client_from_request,
    remove_agent_fga,
    remove_project_fga,
    require_tenant_admin,
    require_tenant_membership,
    resolve_tenant_or_404,
)


async def list_projects_for_tenant_ref(
    request: Request,
    tenant_ref: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, str]], int]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)

    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_membership(
            session,
            tenant_id=tenant.id,
            acting_user_id=acting_user_id,
            request=request,
        )
        projects, total = list_projects_for_tenant(
            session,
            tenant_id=tenant.id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return (
            [{"id": str(p.id), "tenant_id": str(p.tenant_id), "name": p.name} for p in projects],
            total,
        )


async def create_project_for_tenant(request: Request, tenant_id: str, name: str) -> dict[str, str]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_id)
        require_tenant_admin(
            session,
            tenant_id=tenant.id,
            acting_user_id=acting_user_id,
            request=request,
        )
        project = create_project(session, tenant_id=tenant.id, name=name)
        client = openfga_client_from_request(request)
        if client is not None:
            await client.write_tuple(
                user=fga_tenant(str(tenant.id)),
                relation="tenant",
                obj=fga_project(str(project.id)),
            )
        return {"id": str(project.id), "tenant_id": str(project.tenant_id), "name": project.name}


async def delete_project_by_id(request: Request, project_id: str) -> dict[str, Any]:
    acting_user_id = current_user_id_from_request(request)
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        project = get_project(session, project_uuid)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_admin(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        agents = list_agents_for_tenant(session, tenant_id=project.tenant_id)
        for agent in agents:
            if agent.project_id == project.id:
                await remove_agent_fga(request, agent_id=str(agent.id), project_id=str(project.id))
        await remove_project_fga(request, project_id=str(project.id), tenant_id=str(project.tenant_id))
        delete_project(session, project)
        return {"deleted": True, "project_id": str(project_uuid)}
