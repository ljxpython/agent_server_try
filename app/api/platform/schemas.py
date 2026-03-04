from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    slug: str | None = Field(default=None, min_length=2, max_length=128)


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    status: str


class DeleteTenantResponse(BaseModel):
    tenant_id: str
    deleted: bool


class AddMembershipRequest(BaseModel):
    external_subject: str | None = None
    user_id: str | None = None
    email: str | None = None
    role: str = Field(default="member", pattern="^(owner|admin|member)$")


class MembershipResponse(BaseModel):
    tenant_id: str
    user_id: str
    role: str


class MembershipListItemResponse(BaseModel):
    tenant_id: str
    user_id: str
    external_subject: str
    email: str
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
    langgraph_assistant_id: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=2000)


class UpdateAssistantRequest(BaseModel):
    name: str = Field(min_length=2, max_length=128)
    graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)
    langgraph_assistant_id: str = Field(default="", max_length=128)
    description: str = Field(default="", max_length=2000)


class AssistantResponse(BaseModel):
    id: str
    project_id: str
    name: str
    graph_id: str
    runtime_base_url: str
    langgraph_assistant_id: str
    description: str


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
