from __future__ import annotations

from typing import Any, NoReturn

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
from app.services.langgraph_sdk.assistants_service import LangGraphAssistantsService
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    openfga_client_from_request,
    remove_agent_fga,
    require_tenant_admin,
    require_tenant_membership,
)


def _extract_langgraph_assistant_id(response: Any, fallback_id: str = "") -> str:
    # SDK 可能返回 dict 或对象，这里统一提取 canonical assistant_id。
    assistant_id: Any = None
    if isinstance(response, dict):
        assistant_id = response.get("assistant_id")
    else:
        assistant_id = getattr(response, "assistant_id", None)

    if isinstance(assistant_id, str) and assistant_id:
        return assistant_id
    if assistant_id is not None:
        return str(assistant_id)
    return fallback_id


def _raise_langgraph_sync_error(operation: str, context: str = "") -> NoReturn:
    detail = f"langgraph assistant {operation} failed"
    if context:
        detail = f"{detail}: {context}"
    raise HTTPException(status_code=502, detail=detail)


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
                    "langgraph_assistant_id": str(a.langgraph_assistant_id or ""),
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
    langgraph_assistant_id: str = "",
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
        assistants_service = LangGraphAssistantsService(request)
        create_payload = {
            "graph_id": graph_id,
            "name": name,
            "description": description,
        }
        sdk_response: Any = None
        try:
            sdk_response = await assistants_service.create(create_payload)
        except Exception as exc:  # noqa: BLE001 - 统一映射为平台侧 502
            _raise_langgraph_sync_error("create", str(exc)[:120])

        resolved_assistant_id = _extract_langgraph_assistant_id(
            sdk_response,
            fallback_id=langgraph_assistant_id or "",
        )
        agent = create_agent(
            session,
            project_id=project.id,
            name=name,
            graph_id=graph_id,
            runtime_base_url=runtime_base_url,
            description=description,
            langgraph_assistant_id=resolved_assistant_id,
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
            "langgraph_assistant_id": str(agent.langgraph_assistant_id or ""),
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
        existing_assistant_id = str(agent.langgraph_assistant_id or "")
        if existing_assistant_id:
            assistants_service = LangGraphAssistantsService(request)
            try:
                await assistants_service.delete(existing_assistant_id)
            except Exception as exc:  # noqa: BLE001 - 统一映射为平台侧 502
                _raise_langgraph_sync_error("delete", str(exc)[:120])
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
    langgraph_assistant_id: str = "",
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
        existing_assistant_id = str(agent.langgraph_assistant_id or "")
        if existing_assistant_id:
            assistants_service = LangGraphAssistantsService(request)
            update_payload = {
                "graph_id": graph_id,
                "name": name,
                "description": description,
            }
            try:
                await assistants_service.update(existing_assistant_id, update_payload)
            except Exception as exc:  # noqa: BLE001 - 统一映射为平台侧 502
                _raise_langgraph_sync_error("update", str(exc)[:120])
        resolved_assistant_id = langgraph_assistant_id or existing_assistant_id
        updated = update_agent(
            session,
            agent=agent,
            name=name,
            graph_id=graph_id,
            runtime_base_url=runtime_base_url,
            description=description,
            langgraph_assistant_id=resolved_assistant_id,
        )
        return {
            "id": str(updated.id),
            "project_id": str(updated.project_id),
            "name": updated.name,
            "graph_id": updated.graph_id,
            "runtime_base_url": updated.runtime_base_url,
            "langgraph_assistant_id": str(updated.langgraph_assistant_id or ""),
            "description": updated.description,
        }
