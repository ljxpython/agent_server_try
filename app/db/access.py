from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, and_, asc, desc, func, select
from sqlalchemy.orm import Session

from app.db.models import Agent, AuditLog, Membership, Project, RuntimeBinding, Tenant, User


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def get_user_by_external_subject(session: Session, external_subject: str) -> User | None:
    stmt = select(User).where(User.external_subject == external_subject)
    return session.scalar(stmt)


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def upsert_user_from_subject(session: Session, external_subject: str, email: str | None) -> User:
    user = get_user_by_external_subject(session, external_subject)
    fallback_email = f"{external_subject}@local.invalid"

    if user is None:
        user = User(
            external_subject=external_subject,
            email=email or fallback_email,
        )
        session.add(user)
        session.flush()
        return user

    if email and user.email != email:
        user.email = email
        session.flush()

    return user


def resolve_tenant(session: Session, tenant_ref: str) -> Tenant | None:
    tenant_uuid = parse_uuid(tenant_ref)
    if tenant_uuid:
        return session.get(Tenant, tenant_uuid)

    stmt = select(Tenant).where(Tenant.slug == tenant_ref)
    return session.scalar(stmt)


def has_membership(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    stmt = select(Membership.id).where(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
    )
    return session.scalar(stmt) is not None


def get_membership(session: Session, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Membership | None:
    stmt = select(Membership).where(
        Membership.tenant_id == tenant_id,
        Membership.user_id == user_id,
    )
    return session.scalar(stmt)


def create_tenant(session: Session, name: str, slug: str) -> Tenant:
    tenant = Tenant(name=name, slug=slug, status="active")
    session.add(tenant)
    session.flush()
    return tenant


def create_or_update_membership(
    session: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    role: str,
) -> Membership:
    membership = get_membership(session, tenant_id=tenant_id, user_id=user_id)
    if membership is None:
        membership = Membership(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
        )
        session.add(membership)
        session.flush()
        return membership

    if membership.role != role:
        membership.role = role
        session.flush()
    return membership


def list_tenants_for_user(
    session: Session,
    user_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Tenant], int]:
    order_column = Tenant.name if sort_by == "name" else Tenant.created_at
    order_expr = asc(order_column) if sort_order == "asc" else desc(order_column)

    base_stmt = select(Tenant).join(Membership, Membership.tenant_id == Tenant.id).where(Membership.user_id == user_id)
    stmt = base_stmt.order_by(order_expr).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def list_projects_for_tenant(
    session: Session,
    tenant_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Project], int]:
    order_column = Project.name if sort_by == "name" else Project.created_at
    order_expr = asc(order_column) if sort_order == "asc" else desc(order_column)
    base_stmt = select(Project).where(Project.tenant_id == tenant_id)
    stmt = base_stmt.order_by(order_expr).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def create_project(session: Session, tenant_id: uuid.UUID, name: str) -> Project:
    project = Project(tenant_id=tenant_id, name=name)
    session.add(project)
    session.flush()
    return project


def get_project(session: Session, project_id: uuid.UUID) -> Project | None:
    return session.get(Project, project_id)


def delete_project(session: Session, project: Project) -> None:
    session.delete(project)
    session.flush()


def list_agents_for_project(
    session: Session,
    project_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[Agent], int]:
    order_column = Agent.name if sort_by == "name" else Agent.created_at
    order_expr = asc(order_column) if sort_order == "asc" else desc(order_column)
    base_stmt = select(Agent).where(Agent.project_id == project_id)
    stmt = base_stmt.order_by(order_expr).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_agent(session: Session, agent_id: uuid.UUID) -> Agent | None:
    return session.get(Agent, agent_id)


def get_agent_with_project(session: Session, agent_id: uuid.UUID) -> tuple[Agent, Project] | None:
    stmt = (
        select(Agent, Project)
        .join(Project, Agent.project_id == Project.id)
        .where(Agent.id == agent_id)
    )
    row = session.execute(stmt).first()
    if row is None:
        return None
    return row[0], row[1]


def list_agents_for_tenant(session: Session, tenant_id: uuid.UUID) -> list[Agent]:
    stmt = (
        select(Agent)
        .join(Project, Agent.project_id == Project.id)
        .where(Project.tenant_id == tenant_id)
        .order_by(Agent.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def delete_agent(session: Session, agent: Agent) -> None:
    session.delete(agent)
    session.flush()


def create_agent(
    session: Session,
    project_id: uuid.UUID,
    name: str,
    graph_id: str,
    runtime_base_url: str,
    description: str,
) -> Agent:
    agent = Agent(
        project_id=project_id,
        name=name,
        graph_id=graph_id,
        runtime_base_url=runtime_base_url,
        description=description,
    )
    session.add(agent)
    session.flush()
    return agent


def list_runtime_bindings(
    session: Session,
    agent_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> tuple[list[RuntimeBinding], int]:
    order_column = RuntimeBinding.environment if sort_by == "environment" else RuntimeBinding.created_at
    order_expr = asc(order_column) if sort_order == "asc" else desc(order_column)
    base_stmt = select(RuntimeBinding).where(RuntimeBinding.agent_id == agent_id)
    stmt = base_stmt.order_by(order_expr).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def create_or_update_runtime_binding(
    session: Session,
    agent_id: uuid.UUID,
    environment: str,
    langgraph_assistant_id: str,
    langgraph_graph_id: str,
    runtime_base_url: str,
) -> RuntimeBinding:
    stmt = select(RuntimeBinding).where(
        RuntimeBinding.agent_id == agent_id,
        RuntimeBinding.environment == environment,
    )
    binding = session.scalar(stmt)
    if binding is None:
        binding = RuntimeBinding(
            agent_id=agent_id,
            environment=environment,
            langgraph_assistant_id=langgraph_assistant_id,
            langgraph_graph_id=langgraph_graph_id,
            runtime_base_url=runtime_base_url,
        )
        session.add(binding)
        session.flush()
        return binding

    binding.langgraph_assistant_id = langgraph_assistant_id
    binding.langgraph_graph_id = langgraph_graph_id
    binding.runtime_base_url = runtime_base_url
    session.flush()
    return binding


def delete_membership(session: Session, membership: Membership) -> None:
    session.delete(membership)
    session.flush()


def create_audit_log(
    session: Session,
    request_id: str,
    plane: str,
    method: str,
    path: str,
    query: str,
    status_code: int,
    duration_ms: int,
    tenant_id: uuid.UUID | None,
    user_id: uuid.UUID | None,
    user_subject: str | None,
    client_ip: str | None,
    user_agent: str | None,
    response_size: int | None,
    metadata_json: dict | None,
) -> AuditLog:
    log = AuditLog(
        request_id=request_id,
        plane=plane,
        method=method,
        path=path,
        query=query,
        status_code=status_code,
        duration_ms=duration_ms,
        tenant_id=tenant_id,
        user_id=user_id,
        user_subject=user_subject,
        client_ip=client_ip,
        user_agent=user_agent,
        response_size=response_size,
        metadata_json=metadata_json,
    )
    session.add(log)
    session.flush()
    return log


def list_audit_logs(
    session: Session,
    tenant_id: uuid.UUID,
    limit: int,
    offset: int,
    plane: str | None = None,
    method: str | None = None,
    path_prefix: str | None = None,
    status_code: int | None = None,
    user_id: uuid.UUID | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> tuple[list[AuditLog], int]:
    filters = [AuditLog.tenant_id == tenant_id]
    if plane:
        filters.append(AuditLog.plane == plane)
    if method:
        filters.append(AuditLog.method == method.upper())
    if path_prefix:
        filters.append(AuditLog.path.like(f"{path_prefix}%"))
    if status_code is not None:
        filters.append(AuditLog.status_code == status_code)
    if user_id is not None:
        filters.append(AuditLog.user_id == user_id)
    if from_time is not None:
        filters.append(AuditLog.created_at >= from_time)
    if to_time is not None:
        filters.append(AuditLog.created_at <= to_time)

    where_expr = and_(*filters)

    stmt = (
        select(AuditLog)
        .where(where_expr)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    count_stmt = select(func.count()).select_from(AuditLog).where(where_expr)
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def aggregate_audit_logs(
    session: Session,
    tenant_id: uuid.UUID,
    by: str,
    limit: int,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
) -> list[tuple[str, int]]:
    filters = [AuditLog.tenant_id == tenant_id]
    if from_time is not None:
        filters.append(AuditLog.created_at >= from_time)
    if to_time is not None:
        filters.append(AuditLog.created_at <= to_time)

    where_expr = and_(*filters)

    if by == "path":
        key_expr = AuditLog.path
    elif by == "status_code":
        key_expr = func.cast(AuditLog.status_code, String)
    elif by == "user_id":
        key_expr = func.coalesce(func.cast(AuditLog.user_id, String), "anonymous")
    elif by == "plane":
        key_expr = AuditLog.plane
    else:
        key_expr = AuditLog.path

    stmt = (
        select(key_expr.label("k"), func.count().label("c"))
        .where(where_expr)
        .group_by(key_expr)
        .order_by(func.count().desc())
        .limit(limit)
    )

    rows = session.execute(stmt).all()
    return [(str(k), int(c)) for k, c in rows]
