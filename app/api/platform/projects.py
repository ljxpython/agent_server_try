from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from app.services.platform_service import (
    create_project_for_tenant,
    delete_project_by_id,
    list_projects_for_tenant_ref,
    update_project_by_id,
)

from .common import logger, request_id
from .schemas import CreateProjectRequest, ProjectResponse, UpdateProjectRequest


router = APIRouter()


@router.get("/tenants/{tenant_ref}/projects", response_model=list[ProjectResponse])
async def list_projects(
    request: Request,
    response: Response,
    tenant_ref: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    """列出租户下的项目列表。

    参数说明：
    - tenant_ref: 租户引用（id 或 slug）。
    - limit/offset/sort_by/sort_order: 分页与排序参数。

    返回语义：
    - 返回项目列表。
    - 通过响应头 `x-total-count` 返回总数。
    """
    logger.info(
        "platform_list_projects request_id=%s tenant_ref=%s limit=%s offset=%s",
        request_id(request),
        tenant_ref,
        limit,
        offset,
    )
    rows, total = await list_projects_for_tenant_ref(request, tenant_ref, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [ProjectResponse(**row) for row in rows]


@router.post("/projects", response_model=ProjectResponse)
async def create_project_endpoint(request: Request, payload: CreateProjectRequest):
    """在指定租户下创建项目。"""
    logger.info(
        "platform_create_project request_id=%s tenant_id=%s name=%s",
        request_id(request),
        payload.tenant_id,
        payload.name,
    )
    row = await create_project_for_tenant(request, payload.tenant_id, payload.name)
    return ProjectResponse(**row)


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(request: Request, project_id: str):
    """删除项目。"""
    logger.info(
        "platform_delete_project request_id=%s project_id=%s",
        request_id(request),
        project_id,
    )
    return await delete_project_by_id(request, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(request: Request, project_id: str, payload: UpdateProjectRequest):
    """更新项目名称。"""
    logger.info(
        "platform_update_project request_id=%s project_id=%s name=%s",
        request_id(request),
        project_id,
        payload.name,
    )
    row = await update_project_by_id(request, project_id, payload.name)
    return ProjectResponse(**row)
