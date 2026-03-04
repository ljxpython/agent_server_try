from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from app.services.platform_service import (
    create_agent_for_project,
    delete_agent_by_id,
    list_agents_for_project_id,
    update_agent_by_id,
)

from .common import logger, request_id
from .schemas import (
    AssistantResponse,
    CreateAssistantRequest,
    UpdateAssistantRequest,
)


router = APIRouter()


@router.get("/projects/{project_id}/assistants", response_model=list[AssistantResponse])
async def list_assistants(
    request: Request,
    response: Response,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    """列出项目下的 assistants。"""
    logger.info(
        "platform_list_assistants request_id=%s project_id=%s limit=%s offset=%s",
        request_id(request),
        project_id,
        limit,
        offset,
    )
    rows, total = await list_agents_for_project_id(request, project_id, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [AssistantResponse(**row) for row in rows]


@router.post("/assistants", response_model=AssistantResponse)
async def create_assistant_endpoint(request: Request, payload: CreateAssistantRequest):
    """创建 assistant，并关联到指定 project。"""
    logger.info(
        "platform_create_assistant request_id=%s project_id=%s name=%s graph_id=%s",
        request_id(request),
        payload.project_id,
        payload.name,
        payload.graph_id,
    )
    row = await create_agent_for_project(
        request,
        project_id=payload.project_id,
        name=payload.name,
        graph_id=payload.graph_id,
        runtime_base_url=payload.runtime_base_url,
        langgraph_assistant_id=payload.langgraph_assistant_id or "",
        description=payload.description,
    )
    return AssistantResponse(**row)


@router.delete("/assistants/{assistant_id}")
async def delete_assistant_endpoint(request: Request, assistant_id: str):
    """删除 assistant。"""
    logger.info(
        "platform_delete_assistant request_id=%s assistant_id=%s",
        request_id(request),
        assistant_id,
    )
    row = await delete_agent_by_id(request, assistant_id)
    return {
        "deleted": bool(row.get("deleted")),
        "assistant_id": str(row.get("agent_id", "")),
    }


@router.patch("/assistants/{assistant_id}", response_model=AssistantResponse)
async def update_assistant_endpoint(request: Request, assistant_id: str, payload: UpdateAssistantRequest):
    """更新 assistant 基础信息。"""
    logger.info(
        "platform_update_assistant request_id=%s assistant_id=%s name=%s graph_id=%s",
        request_id(request),
        assistant_id,
        payload.name,
        payload.graph_id,
    )
    row = await update_agent_by_id(
        request,
        agent_id=assistant_id,
        name=payload.name,
        graph_id=payload.graph_id,
        runtime_base_url=payload.runtime_base_url,
        langgraph_assistant_id=payload.langgraph_assistant_id or "",
        description=payload.description,
    )
    return AssistantResponse(**row)
