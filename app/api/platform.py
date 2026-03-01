from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.services.platform_service import (
    add_membership_to_tenant,
    create_agent_for_project,
    create_project_for_tenant,
    create_tenant_for_current_user,
    delete_agent_by_id,
    delete_project_by_id,
    delete_runtime_binding_by_id,
    export_tenant_audit_logs_csv,
    list_agent_bindings_by_agent_id,
    list_agents_for_project_id,
    list_my_tenants,
    list_projects_for_tenant_ref,
    query_tenant_audit_logs_data,
    query_tenant_audit_stats_data,
    remove_membership_from_tenant,
    upsert_agent_binding_by_agent_id,
    update_agent_by_id,
    update_project_by_id,
)


router = APIRouter(prefix="/_platform", tags=["platform"])
logger = logging.getLogger("proxy.platform")


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    slug: str | None = Field(default=None, min_length=2, max_length=128)


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str


class AddMembershipRequest(BaseModel):
    external_subject: str | None = None
    user_id: str | None = None
    email: str | None = None
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class MembershipResponse(BaseModel):
    tenant_id: str
    user_id: str
    role: str


class DeleteMembershipResponse(BaseModel):
    tenant_id: str
    user_id: str
    deleted: bool


class CreateProjectRequest(BaseModel):
    tenant_id: str
    name: str = Field(min_length=2, max_length=128)


class UpdateProjectRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    name: str


class CreateAssistantRequest(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=128)
    graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)
    description: str = Field(default="", max_length=2000)


class UpdateAssistantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)
    description: str = Field(default="", max_length=2000)


class AssistantResponse(BaseModel):
    id: str
    project_id: str
    name: str
    graph_id: str
    runtime_base_url: str
    description: str


class UpsertEnvironmentMappingRequest(BaseModel):
    environment: str = Field(default="dev", pattern="^(dev|staging|prod)$")
    langgraph_assistant_id: str = Field(min_length=2, max_length=128)
    langgraph_graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)


class EnvironmentMappingResponse(BaseModel):
    id: str
    assistant_id: str
    environment: str
    langgraph_assistant_id: str
    langgraph_graph_id: str
    runtime_base_url: str


class DeleteEnvironmentMappingResponse(BaseModel):
    deleted: bool
    binding_id: str


class AuditLogResponse(BaseModel):
    id: str
    request_id: str
    plane: str
    method: str
    path: str
    query: str
    status_code: int
    duration_ms: int
    tenant_id: str | None
    user_id: str | None
    user_subject: str | None
    client_ip: str | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[AuditLogResponse]


class AuditStatItem(BaseModel):
    key: str
    count: int


class AuditStatsResponse(BaseModel):
    by: str
    items: list[AuditStatItem]


@router.get("/tenants", response_model=list[TenantResponse])
async def list_my_tenants_endpoint(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    logger.info(
        "platform_list_tenants request_id=%s limit=%s offset=%s sort_by=%s sort_order=%s",
        getattr(request.state, "request_id", "-"),
        limit,
        offset,
        sort_by,
        sort_order,
    )
    rows, total = await list_my_tenants(request, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [TenantResponse(**row) for row in rows]


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant_endpoint(request: Request, payload: CreateTenantRequest):
    logger.info(
        "platform_create_tenant request_id=%s name=%s slug=%s",
        getattr(request.state, "request_id", "-"),
        payload.name,
        payload.slug,
    )
    row = await create_tenant_for_current_user(request, payload.name, payload.slug)
    return TenantResponse(**row)


@router.post("/tenants/{tenant_ref}/memberships", response_model=MembershipResponse)
async def add_membership(request: Request, tenant_ref: str, payload: AddMembershipRequest):
    logger.info(
        "platform_add_membership request_id=%s tenant_ref=%s role=%s user_id=%s external_subject=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        payload.role,
        payload.user_id,
        payload.external_subject,
    )
    row = await add_membership_to_tenant(
        request,
        tenant_ref=tenant_ref,
        role=payload.role,
        external_subject=payload.external_subject,
        user_id=payload.user_id,
        email=payload.email,
    )
    return MembershipResponse(**row)


@router.delete("/tenants/{tenant_ref}/memberships/{user_ref}", response_model=DeleteMembershipResponse)
async def remove_membership(request: Request, tenant_ref: str, user_ref: str):
    logger.info(
        "platform_remove_membership request_id=%s tenant_ref=%s user_ref=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        user_ref,
    )
    row = await remove_membership_from_tenant(request, tenant_ref, user_ref)
    return DeleteMembershipResponse(**row)


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
    logger.info(
        "platform_list_projects request_id=%s tenant_ref=%s limit=%s offset=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        limit,
        offset,
    )
    rows, total = await list_projects_for_tenant_ref(request, tenant_ref, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [ProjectResponse(**row) for row in rows]


@router.post("/projects", response_model=ProjectResponse)
async def create_project_endpoint(request: Request, payload: CreateProjectRequest):
    logger.info(
        "platform_create_project request_id=%s tenant_id=%s name=%s",
        getattr(request.state, "request_id", "-"),
        payload.tenant_id,
        payload.name,
    )
    row = await create_project_for_tenant(request, payload.tenant_id, payload.name)
    return ProjectResponse(**row)


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(request: Request, project_id: str):
    logger.info(
        "platform_delete_project request_id=%s project_id=%s",
        getattr(request.state, "request_id", "-"),
        project_id,
    )
    return await delete_project_by_id(request, project_id)


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
async def update_project_endpoint(request: Request, project_id: str, payload: UpdateProjectRequest):
    logger.info(
        "platform_update_project request_id=%s project_id=%s name=%s",
        getattr(request.state, "request_id", "-"),
        project_id,
        payload.name,
    )
    row = await update_project_by_id(request, project_id, payload.name)
    return ProjectResponse(**row)


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
    logger.info(
        "platform_list_assistants request_id=%s project_id=%s limit=%s offset=%s",
        getattr(request.state, "request_id", "-"),
        project_id,
        limit,
        offset,
    )
    rows, total = await list_agents_for_project_id(request, project_id, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [AssistantResponse(**row) for row in rows]


@router.post("/assistants", response_model=AssistantResponse)
async def create_assistant_endpoint(request: Request, payload: CreateAssistantRequest):
    logger.info(
        "platform_create_assistant request_id=%s project_id=%s name=%s graph_id=%s",
        getattr(request.state, "request_id", "-"),
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
        description=payload.description,
    )
    return AssistantResponse(**row)


@router.delete("/assistants/{assistant_id}")
async def delete_assistant_endpoint(request: Request, assistant_id: str):
    logger.info(
        "platform_delete_assistant request_id=%s assistant_id=%s",
        getattr(request.state, "request_id", "-"),
        assistant_id,
    )
    row = await delete_agent_by_id(request, assistant_id)
    return {
        "deleted": bool(row.get("deleted")),
        "assistant_id": str(row.get("agent_id", "")),
    }


@router.patch("/assistants/{assistant_id}", response_model=AssistantResponse)
async def update_assistant_endpoint(request: Request, assistant_id: str, payload: UpdateAssistantRequest):
    logger.info(
        "platform_update_assistant request_id=%s assistant_id=%s name=%s graph_id=%s",
        getattr(request.state, "request_id", "-"),
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
        description=payload.description,
    )
    return AssistantResponse(**row)


@router.get("/assistants/{assistant_id}/environment-mappings", response_model=list[EnvironmentMappingResponse])
async def list_environment_mappings(
    request: Request,
    response: Response,
    assistant_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|environment)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    logger.info(
        "platform_list_environment_mappings request_id=%s assistant_id=%s",
        getattr(request.state, "request_id", "-"),
        assistant_id,
    )
    rows, total = await list_agent_bindings_by_agent_id(request, assistant_id, limit, offset, sort_by, sort_order)
    response.headers["x-total-count"] = str(total)
    return [
        EnvironmentMappingResponse(
            id=row["id"],
            assistant_id=row["agent_id"],
            environment=row["environment"],
            langgraph_assistant_id=row["langgraph_assistant_id"],
            langgraph_graph_id=row["langgraph_graph_id"],
            runtime_base_url=row["runtime_base_url"],
        )
        for row in rows
    ]


@router.post("/assistants/{assistant_id}/environment-mappings", response_model=EnvironmentMappingResponse)
async def upsert_environment_mapping(
    request: Request,
    assistant_id: str,
    payload: UpsertEnvironmentMappingRequest,
):
    logger.info(
        "platform_upsert_environment_mapping request_id=%s assistant_id=%s env=%s graph_id=%s",
        getattr(request.state, "request_id", "-"),
        assistant_id,
        payload.environment,
        payload.langgraph_graph_id,
    )
    row = await upsert_agent_binding_by_agent_id(
        request,
        agent_id=assistant_id,
        environment=payload.environment,
        langgraph_assistant_id=payload.langgraph_assistant_id,
        langgraph_graph_id=payload.langgraph_graph_id,
        runtime_base_url=payload.runtime_base_url,
    )
    return EnvironmentMappingResponse(
        id=row["id"],
        assistant_id=row["agent_id"],
        environment=row["environment"],
        langgraph_assistant_id=row["langgraph_assistant_id"],
        langgraph_graph_id=row["langgraph_graph_id"],
        runtime_base_url=row["runtime_base_url"],
    )


@router.delete(
    "/assistants/{assistant_id}/environment-mappings/{mapping_id}",
    response_model=DeleteEnvironmentMappingResponse,
)
async def delete_environment_mapping_endpoint(request: Request, assistant_id: str, mapping_id: str):
    logger.info(
        "platform_delete_environment_mapping request_id=%s assistant_id=%s mapping_id=%s",
        getattr(request.state, "request_id", "-"),
        assistant_id,
        mapping_id,
    )
    row = await delete_runtime_binding_by_id(request, agent_id=assistant_id, binding_id=mapping_id)
    return DeleteEnvironmentMappingResponse(
        deleted=bool(row.get("deleted")),
        binding_id=str(row.get("binding_id", "")),
    )


@router.get("/tenants/{tenant_ref}/audit-logs", response_model=AuditLogListResponse)
async def query_tenant_audit_logs(
    request: Request,
    tenant_ref: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    plane: str | None = Query(default=None, pattern="^(control_plane|runtime_proxy|internal)$"),
    method: str | None = Query(default=None, pattern="^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$"),
    path_prefix: str | None = None,
    status_code: int | None = Query(default=None, ge=100, le=599),
    user_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
):
    logger.info(
        "platform_query_audit_logs request_id=%s tenant_ref=%s limit=%s offset=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        limit,
        offset,
    )
    row = await query_tenant_audit_logs_data(
        request,
        tenant_ref=tenant_ref,
        limit=limit,
        offset=offset,
        plane=plane,
        method=method,
        path_prefix=path_prefix,
        status_code=status_code,
        user_id=user_id,
        from_time=from_time,
        to_time=to_time,
    )
    return AuditLogListResponse(**row)


@router.get("/tenants/{tenant_ref}/audit-logs/stats", response_model=AuditStatsResponse)
async def query_tenant_audit_stats(
    request: Request,
    tenant_ref: str,
    by: str = Query(default="path", pattern="^(path|status_code|user_id|plane)$"),
    limit: int = Query(default=20, ge=1, le=100),
    from_time: datetime | None = None,
    to_time: datetime | None = None,
):
    logger.info(
        "platform_query_audit_stats request_id=%s tenant_ref=%s by=%s limit=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        by,
        limit,
    )
    row = await query_tenant_audit_stats_data(
        request,
        tenant_ref=tenant_ref,
        by=by,
        limit=limit,
        from_time=from_time,
        to_time=to_time,
    )
    return AuditStatsResponse(**row)


@router.get("/tenants/{tenant_ref}/audit-logs/export")
async def export_tenant_audit_logs(
    request: Request,
    tenant_ref: str,
    plane: str | None = Query(default=None, pattern="^(control_plane|runtime_proxy|internal)$"),
    method: str | None = Query(default=None, pattern="^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)$"),
    path_prefix: str | None = None,
    status_code: int | None = Query(default=None, ge=100, le=599),
    user_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    max_rows: int = Query(default=5000, ge=1, le=20000),
):
    logger.info(
        "platform_export_audit_logs request_id=%s tenant_ref=%s max_rows=%s",
        getattr(request.state, "request_id", "-"),
        tenant_ref,
        max_rows,
    )
    csv_text, filename = await export_tenant_audit_logs_csv(
        request,
        tenant_ref=tenant_ref,
        plane=plane,
        method=method,
        path_prefix=path_prefix,
        status_code=status_code,
        user_id=user_id,
        from_time=from_time,
        to_time=to_time,
        max_rows=max_rows,
    )
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
