from __future__ import annotations

from fastapi import HTTPException, Request

from app.db.access import (
    create_or_update_runtime_binding,
    delete_runtime_binding,
    get_agent,
    get_project,
    get_runtime_binding,
    list_runtime_bindings,
    parse_uuid,
)
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    require_tenant_admin,
    require_tenant_membership,
)


async def list_agent_bindings_by_agent_id(
    request: Request,
    agent_id: str,
    limit: int,
    offset: int,
    sort_by: str,
    sort_order: str,
) -> tuple[list[dict[str, str]], int]:
    acting_user_id = current_user_id_from_request(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_membership(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        bindings, total = list_runtime_bindings(
            session,
            agent_id=agent_uuid,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return (
            [
                {
                    "id": str(b.id),
                    "agent_id": str(b.agent_id),
                    "environment": b.environment,
                    "langgraph_assistant_id": b.langgraph_assistant_id,
                    "langgraph_graph_id": b.langgraph_graph_id,
                    "runtime_base_url": b.runtime_base_url,
                }
                for b in bindings
            ],
            total,
        )


async def upsert_agent_binding_by_agent_id(
    request: Request,
    agent_id: str,
    environment: str,
    langgraph_assistant_id: str,
    langgraph_graph_id: str,
    runtime_base_url: str,
) -> dict[str, str]:
    acting_user_id = current_user_id_from_request(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_admin(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )
        binding = create_or_update_runtime_binding(
            session,
            agent_id=agent.id,
            environment=environment,
            langgraph_assistant_id=langgraph_assistant_id,
            langgraph_graph_id=langgraph_graph_id,
            runtime_base_url=runtime_base_url,
        )
        return {
            "id": str(binding.id),
            "agent_id": str(binding.agent_id),
            "environment": binding.environment,
            "langgraph_assistant_id": binding.langgraph_assistant_id,
            "langgraph_graph_id": binding.langgraph_graph_id,
            "runtime_base_url": binding.runtime_base_url,
        }


async def delete_runtime_binding_by_id(request: Request, agent_id: str, binding_id: str) -> dict[str, str | bool]:
    acting_user_id = current_user_id_from_request(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")
    binding_uuid = parse_uuid(binding_id)
    if binding_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid binding_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        require_tenant_admin(
            session,
            tenant_id=project.tenant_id,
            acting_user_id=acting_user_id,
            request=request,
        )

        binding = get_runtime_binding(session, binding_uuid)
        if binding is None or binding.agent_id != agent.id:
            raise HTTPException(status_code=404, detail="Runtime binding not found")

        delete_runtime_binding(session, binding)
        return {"deleted": True, "binding_id": str(binding_uuid)}
