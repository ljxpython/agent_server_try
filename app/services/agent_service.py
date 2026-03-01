from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.auth.openfga import fga_agent, fga_project
from app.db.access import (
    create_agent,
    delete_agent,
    get_agent,
    get_project,
    list_agents_for_project,
    parse_uuid,
    update_agent,
)
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    openfga_client_from_request,
    remove_agent_fga,
    require_tenant_admin,
    require_tenant_membership,
)


async def list_agents_for_project_id(
    request: Request,
    project_id: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, str]], int]:
    acting_user_id = current_user_id_from_request(request)
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        project = get_project(session, project_uuid)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_membership(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        agents, total = list_agents_for_project(
            session,
            project_id=project_uuid,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return (
            [
                {
                    "id": str(a.id),
                    "project_id": str(a.project_id),
                    "name": a.name,
                    "graph_id": a.graph_id,
                    "runtime_base_url": a.runtime_base_url,
                    "description": a.description,
                }
                for a in agents
            ],
            total,
        )


async def create_agent_for_project(
    request: Request,
    project_id: str,
    name: str,
    graph_id: str,
    runtime_base_url: str,
    description: str,
) -> dict[str, str]:
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
        agent = create_agent(
            session,
            project_id=project.id,
            name=name,
            graph_id=graph_id,
            runtime_base_url=runtime_base_url,
            description=description,
        )
        client = openfga_client_from_request(request)
        if client is not None:
            await client.write_tuple(
                user=fga_project(str(project.id)),
                relation="project",
                obj=fga_agent(str(agent.id)),
            )
        return {
            "id": str(agent.id),
            "project_id": str(agent.project_id),
            "name": agent.name,
            "graph_id": agent.graph_id,
            "runtime_base_url": agent.runtime_base_url,
            "description": agent.description,
        }


async def delete_agent_by_id(request: Request, agent_id: str) -> dict[str, Any]:
    acting_user_id = current_user_id_from_request(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid assistant_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_admin(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        await remove_agent_fga(request, agent_id=str(agent.id), project_id=str(project.id))
        delete_agent(session, agent)
        return {"deleted": True, "agent_id": str(agent_uuid)}


async def update_agent_by_id(
    request: Request,
    agent_id: str,
    name: str,
    graph_id: str,
    runtime_base_url: str,
    description: str,
) -> dict[str, str]:
    acting_user_id = current_user_id_from_request(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid assistant_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Assistant not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_admin(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        updated = update_agent(
            session,
            agent=agent,
            name=name,
            graph_id=graph_id,
            runtime_base_url=runtime_base_url,
            description=description,
        )
        return {
            "id": str(updated.id),
            "project_id": str(updated.project_id),
            "name": updated.name,
            "graph_id": updated.graph_id,
            "runtime_base_url": updated.runtime_base_url,
            "description": updated.description,
        }
