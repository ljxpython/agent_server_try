from __future__ import annotations

import re
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.auth.openfga import fga_agent, fga_project, fga_tenant, fga_user
from app.db.access import (
    create_agent,
    create_or_update_membership,
    create_or_update_runtime_binding,
    create_project,
    create_tenant,
    delete_agent,
    delete_membership,
    delete_project,
    get_agent,
    get_membership,
    get_project,
    get_user_by_id,
    get_user_by_external_subject,
    list_agents_for_tenant,
    list_agents_for_project,
    list_audit_logs,
    list_projects_for_tenant,
    list_runtime_bindings,
    list_tenants_for_user,
    parse_uuid,
    resolve_tenant,
    upsert_user_from_subject,
)
from app.db.session import session_scope


router = APIRouter(prefix="/_platform", tags=["platform"])


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


class ProjectResponse(BaseModel):
    id: str
    tenant_id: str
    name: str


class CreateAgentRequest(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=128)
    graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)
    description: str = Field(default="", max_length=2000)


class AgentResponse(BaseModel):
    id: str
    project_id: str
    name: str
    graph_id: str
    runtime_base_url: str
    description: str


class UpsertRuntimeBindingRequest(BaseModel):
    environment: str = Field(default="dev", pattern="^(dev|staging|prod)$")
    langgraph_assistant_id: str = Field(min_length=2, max_length=128)
    langgraph_graph_id: str = Field(min_length=2, max_length=128)
    runtime_base_url: str = Field(min_length=10, max_length=512)


class RuntimeBindingResponse(BaseModel):
    id: str
    agent_id: str
    environment: str
    langgraph_assistant_id: str
    langgraph_graph_id: str
    runtime_base_url: str


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


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug or uuid.uuid4().hex[:12]


def _db_session_factory(request: Request):
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not enabled")
    return session_factory


def _current_user_id(request: Request) -> uuid.UUID:
    user_id = getattr(request.state, "user_id", None)
    parsed = parse_uuid(str(user_id) if user_id else "")
    if parsed is None:
        raise HTTPException(status_code=401, detail="Authenticated user is required")
    return parsed


def _openfga_client(request: Request):
    return getattr(request.app.state, "openfga_client", None)


async def _sync_tenant_membership_fga(request: Request, tenant_id: str, user_subject: str, role: str) -> None:
    client = _openfga_client(request)
    if client is None:
        return

    user = fga_user(user_subject)
    tenant = fga_tenant(tenant_id)
    role_relations = ["owner", "admin", "member"]
    await client.delete_tuples(
        [
            {"user": user, "relation": rel, "object": tenant}
            for rel in role_relations
        ]
    )
    await client.write_tuple(user=user, relation=role, obj=tenant)


async def _remove_tenant_membership_fga(request: Request, tenant_id: str, user_subject: str) -> None:
    client = _openfga_client(request)
    if client is None:
        return
    user = fga_user(user_subject)
    tenant = fga_tenant(tenant_id)
    await client.delete_tuples(
        [
            {"user": user, "relation": "owner", "object": tenant},
            {"user": user, "relation": "admin", "object": tenant},
            {"user": user, "relation": "member", "object": tenant},
        ]
    )


async def _remove_project_fga(request: Request, project_id: str, tenant_id: str) -> None:
    client = _openfga_client(request)
    if client is None:
        return
    await client.delete_tuple(
        user=fga_tenant(tenant_id),
        relation="tenant",
        obj=fga_project(project_id),
    )


async def _remove_agent_fga(request: Request, agent_id: str, project_id: str) -> None:
    client = _openfga_client(request)
    if client is None:
        return
    await client.delete_tuple(
        user=fga_project(project_id),
        relation="project",
        obj=fga_agent(agent_id),
    )


def _resolve_tenant_or_404(session, tenant_ref: str):
    tenant = resolve_tenant(session, tenant_ref)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _require_tenant_membership(session, tenant_id: uuid.UUID, acting_user_id: uuid.UUID):
    membership = get_membership(session, tenant_id=tenant_id, user_id=acting_user_id)
    if membership is None:
        raise HTTPException(status_code=403, detail="Tenant membership required")
    return membership


def _require_tenant_admin(session, tenant_id: uuid.UUID, acting_user_id: uuid.UUID):
    membership = _require_tenant_membership(session, tenant_id, acting_user_id)
    if membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Only owner/admin can perform this action")
    return membership


@router.get("/tenants", response_model=list[TenantResponse])
async def list_my_tenants(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)

    with session_scope(session_factory) as session:
        tenants, total = list_tenants_for_user(
            session,
            user_id=user_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        response.headers["x-total-count"] = str(total)
        return [
            TenantResponse(
                id=str(t.id),
                name=t.name,
                slug=t.slug,
                status=t.status,
            )
            for t in tenants
        ]


@router.post("/tenants", response_model=TenantResponse)
async def create_tenant_endpoint(request: Request, payload: CreateTenantRequest):
    user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)
    slug = payload.slug or _slugify(payload.name)

    with session_scope(session_factory) as session:
        try:
            tenant = create_tenant(session, name=payload.name, slug=slug)
            create_or_update_membership(
                session,
                tenant_id=tenant.id,
                user_id=user_id,
                role="owner",
            )
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail=f"Tenant slug already exists: {slug}") from exc

        if getattr(request.state, "user_subject", None):
            await _sync_tenant_membership_fga(
                request,
                tenant_id=str(tenant.id),
                user_subject=str(request.state.user_subject),
                role="owner",
            )

        return TenantResponse(
            id=str(tenant.id),
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
        )


@router.post("/tenants/{tenant_ref}/memberships", response_model=MembershipResponse)
async def add_membership(request: Request, tenant_ref: str, payload: AddMembershipRequest):
    acting_user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)

    with session_scope(session_factory) as session:
        tenant = _resolve_tenant_or_404(session, tenant_ref)
        _require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        target_user = None
        target_uuid = parse_uuid(payload.user_id or "") if payload.user_id else None
        if target_uuid is not None:
            target_user = get_user_by_id(session, target_uuid)

        if target_user is None and payload.external_subject:
            target_user = get_user_by_external_subject(session, payload.external_subject)

        if target_user is None and payload.external_subject:
            target_user = upsert_user_from_subject(
                session,
                external_subject=payload.external_subject,
                email=payload.email,
            )

        if target_user is None:
            raise HTTPException(status_code=404, detail="Target user not found")

        membership = create_or_update_membership(
            session,
            tenant_id=tenant.id,
            user_id=target_user.id,
            role=payload.role,
        )

        user_subject = payload.external_subject
        if not user_subject:
            user_subject = target_user.external_subject
        await _sync_tenant_membership_fga(
            request,
            tenant_id=str(tenant.id),
            user_subject=str(user_subject),
            role=payload.role,
        )

        return MembershipResponse(
            tenant_id=str(membership.tenant_id),
            user_id=str(membership.user_id),
            role=membership.role,
        )


@router.delete("/tenants/{tenant_ref}/memberships/{user_ref}", response_model=DeleteMembershipResponse)
async def remove_membership(request: Request, tenant_ref: str, user_ref: str):
    acting_user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)

    with session_scope(session_factory) as session:
        tenant = _resolve_tenant_or_404(session, tenant_ref)
        _require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        target_user = None
        user_uuid = parse_uuid(user_ref)
        if user_uuid is not None:
            target_user = get_user_by_id(session, user_uuid)
        if target_user is None:
            target_user = get_user_by_external_subject(session, user_ref)
        if target_user is None:
            raise HTTPException(status_code=404, detail="Target user not found")

        membership = get_membership(session, tenant_id=tenant.id, user_id=target_user.id)
        if membership is None:
            return DeleteMembershipResponse(
                tenant_id=str(tenant.id),
                user_id=str(target_user.id),
                deleted=False,
            )

        delete_membership(session, membership)
        await _remove_tenant_membership_fga(
            request,
            tenant_id=str(tenant.id),
            user_subject=target_user.external_subject,
        )
        return DeleteMembershipResponse(
            tenant_id=str(tenant.id),
            user_id=str(target_user.id),
            deleted=True,
        )


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
    acting_user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)

    with session_scope(session_factory) as session:
        tenant = _resolve_tenant_or_404(session, tenant_ref)
        _require_tenant_membership(session, tenant_id=tenant.id, acting_user_id=acting_user_id)
        projects, total = list_projects_for_tenant(
            session,
            tenant_id=tenant.id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        response.headers["x-total-count"] = str(total)
        return [
            ProjectResponse(id=str(p.id), tenant_id=str(p.tenant_id), name=p.name)
            for p in projects
        ]


@router.post("/projects", response_model=ProjectResponse)
async def create_project_endpoint(request: Request, payload: CreateProjectRequest):
    acting_user_id = _current_user_id(request)
    session_factory = _db_session_factory(request)

    with session_scope(session_factory) as session:
        tenant = _resolve_tenant_or_404(session, payload.tenant_id)
        _require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)
        project = create_project(session, tenant_id=tenant.id, name=payload.name)
        client = _openfga_client(request)
        if client is not None:
            await client.write_tuple(
                user=fga_tenant(str(tenant.id)),
                relation="tenant",
                obj=fga_project(str(project.id)),
            )
        return ProjectResponse(id=str(project.id), tenant_id=str(project.tenant_id), name=project.name)


@router.delete("/projects/{project_id}")
async def delete_project_endpoint(request: Request, project_id: str):
    acting_user_id = _current_user_id(request)
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        project = get_project(session, project_uuid)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_admin(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        agents = list_agents_for_tenant(session, tenant_id=project.tenant_id)
        for agent in agents:
            if agent.project_id == project.id:
                await _remove_agent_fga(request, agent_id=str(agent.id), project_id=str(project.id))
        await _remove_project_fga(request, project_id=str(project.id), tenant_id=str(project.tenant_id))
        delete_project(session, project)
        return {"deleted": True, "project_id": str(project_uuid)}


@router.get("/projects/{project_id}/agents", response_model=list[AgentResponse])
async def list_agents(
    request: Request,
    response: Response,
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    acting_user_id = _current_user_id(request)
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        project = get_project(session, project_uuid)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_membership(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        agents, total = list_agents_for_project(
            session,
            project_id=project_uuid,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        response.headers["x-total-count"] = str(total)
        return [
            AgentResponse(
                id=str(a.id),
                project_id=str(a.project_id),
                name=a.name,
                graph_id=a.graph_id,
                runtime_base_url=a.runtime_base_url,
                description=a.description,
            )
            for a in agents
        ]


@router.post("/agents", response_model=AgentResponse)
async def create_agent_endpoint(request: Request, payload: CreateAgentRequest):
    acting_user_id = _current_user_id(request)
    project_uuid = parse_uuid(payload.project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid project_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        project = get_project(session, project_uuid)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_admin(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        agent = create_agent(
            session,
            project_id=project.id,
            name=payload.name,
            graph_id=payload.graph_id,
            runtime_base_url=payload.runtime_base_url,
            description=payload.description,
        )
        client = _openfga_client(request)
        if client is not None:
            await client.write_tuple(
                user=fga_project(str(project.id)),
                relation="project",
                obj=fga_agent(str(agent.id)),
            )
        return AgentResponse(
            id=str(agent.id),
            project_id=str(agent.project_id),
            name=agent.name,
            graph_id=agent.graph_id,
            runtime_base_url=agent.runtime_base_url,
            description=agent.description,
        )


@router.delete("/agents/{agent_id}")
async def delete_agent_endpoint(request: Request, agent_id: str):
    acting_user_id = _current_user_id(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_admin(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        await _remove_agent_fga(request, agent_id=str(agent.id), project_id=str(project.id))
        delete_agent(session, agent)
        return {"deleted": True, "agent_id": str(agent_uuid)}


@router.get("/agents/{agent_id}/bindings", response_model=list[RuntimeBindingResponse])
async def list_agent_bindings(
    request: Request,
    response: Response,
    agent_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|environment)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    acting_user_id = _current_user_id(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_membership(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        bindings, total = list_runtime_bindings(
            session,
            agent_id=agent_uuid,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        response.headers["x-total-count"] = str(total)
        return [
            RuntimeBindingResponse(
                id=str(b.id),
                agent_id=str(b.agent_id),
                environment=b.environment,
                langgraph_assistant_id=b.langgraph_assistant_id,
                langgraph_graph_id=b.langgraph_graph_id,
                runtime_base_url=b.runtime_base_url,
            )
            for b in bindings
        ]


@router.post("/agents/{agent_id}/bindings", response_model=RuntimeBindingResponse)
async def upsert_agent_binding(request: Request, agent_id: str, payload: UpsertRuntimeBindingRequest):
    acting_user_id = _current_user_id(request)
    agent_uuid = parse_uuid(agent_id)
    if agent_uuid is None:
        raise HTTPException(status_code=400, detail="Invalid agent_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        agent = get_agent(session, agent_uuid)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found")
        project = get_project(session, agent.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        _require_tenant_admin(session, tenant_id=project.tenant_id, acting_user_id=acting_user_id)
        binding = create_or_update_runtime_binding(
            session,
            agent_id=agent.id,
            environment=payload.environment,
            langgraph_assistant_id=payload.langgraph_assistant_id,
            langgraph_graph_id=payload.langgraph_graph_id,
            runtime_base_url=payload.runtime_base_url,
        )
        return RuntimeBindingResponse(
            id=str(binding.id),
            agent_id=str(binding.agent_id),
            environment=binding.environment,
            langgraph_assistant_id=binding.langgraph_assistant_id,
            langgraph_graph_id=binding.langgraph_graph_id,
            runtime_base_url=binding.runtime_base_url,
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
    acting_user_id = _current_user_id(request)
    filter_user_id = parse_uuid(user_id) if user_id else None
    if user_id and filter_user_id is None:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    session_factory = _db_session_factory(request)
    with session_scope(session_factory) as session:
        tenant = _resolve_tenant_or_404(session, tenant_ref)
        _require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        rows, total = list_audit_logs(
            session,
            tenant_id=tenant.id,
            limit=limit,
            offset=offset,
            plane=plane,
            method=method,
            path_prefix=path_prefix,
            status_code=status_code,
            user_id=filter_user_id,
            from_time=from_time,
            to_time=to_time,
        )

        return AuditLogListResponse(
            total=total,
            limit=limit,
            offset=offset,
            items=[
                AuditLogResponse(
                    id=str(r.id),
                    request_id=r.request_id,
                    plane=r.plane,
                    method=r.method,
                    path=r.path,
                    query=r.query,
                    status_code=r.status_code,
                    duration_ms=r.duration_ms,
                    tenant_id=str(r.tenant_id) if r.tenant_id else None,
                    user_id=str(r.user_id) if r.user_id else None,
                    user_subject=r.user_subject,
                    client_ip=r.client_ip,
                    created_at=r.created_at,
                )
                for r in rows
            ],
        )
