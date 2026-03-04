from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import asc, desc, func, select
from sqlalchemy.orm import Session

from app.db.models import Agent, AuditLog, Project, ProjectMember, RefreshToken, Tenant, User


def parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError):
        return None


def get_user_by_username(session: Session, username: str) -> User | None:
    stmt = select(User).where(User.username == username)
    return session.scalar(stmt)


def get_user_by_id(session: Session, user_id: uuid.UUID) -> User | None:
    return session.get(User, user_id)


def create_user_account(
    session: Session,
    username: str,
    password_hash: str,
    *,
    is_super_admin: bool = False,
) -> User:
    user = User(
        username=username,
        password_hash=password_hash,
        status="active",
        is_super_admin=is_super_admin,
        external_subject=username,
        email=None,
    )
    session.add(user)
    session.flush()
    return user


def update_user_password_hash(session: Session, user: User, password_hash: str) -> None:
    user.password_hash = password_hash
    session.flush()


def count_users(session: Session) -> int:
    return int(session.scalar(select(func.count()).select_from(User)) or 0)


def list_users(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    *,
    query: str | None = None,
    status: str | None = None,
    exclude_user_ids: list[uuid.UUID] | None = None,
) -> tuple[list[User], int]:
    base_stmt = select(User)
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(func.lower(User.username).like(normalized_query))
    if isinstance(status, str) and status.strip():
        base_stmt = base_stmt.where(User.status == status.strip())
    if exclude_user_ids:
        base_stmt = base_stmt.where(User.id.notin_(exclude_user_ids))

    stmt = base_stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def create_refresh_token(
    session: Session,
    user_id: uuid.UUID,
    token_id: str,
    ttl_seconds: int,
) -> RefreshToken:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
    row = RefreshToken(user_id=user_id, token_id=token_id, expires_at=expires_at)
    session.add(row)
    session.flush()
    return row


def get_refresh_token(session: Session, token_id: str) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_id == token_id)
    return session.scalar(stmt)


def revoke_refresh_token(session: Session, token_id: str) -> None:
    row = get_refresh_token(session, token_id)
    if row is None:
        return
    if row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
    session.flush()


def revoke_all_refresh_tokens_for_user(session: Session, user_id: uuid.UUID) -> None:
    stmt = select(RefreshToken).where(
        RefreshToken.user_id == user_id,
        RefreshToken.revoked_at.is_(None),
    )
    now = datetime.now(timezone.utc)
    for row in session.scalars(stmt).all():
        row.revoked_at = now
    session.flush()


def get_or_create_default_tenant(session: Session) -> Tenant:
    stmt = select(Tenant).where(Tenant.slug == "__default")
    tenant = session.scalar(stmt)
    if tenant is not None:
        return tenant
    tenant = Tenant(name="Default", slug="__default", status="active")
    session.add(tenant)
    session.flush()
    return tenant


def create_project(
    session: Session,
    tenant_id: uuid.UUID,
    name: str,
    *,
    description: str | None = None,
) -> Project:
    project = Project(
        tenant_id=tenant_id,
        name=name,
        code=None,
        description=(description or "").strip(),
    )
    session.add(project)
    session.flush()
    return project


def list_active_projects(
    session: Session,
    limit: int = 100,
    offset: int = 0,
    *,
    query: str | None = None,
) -> tuple[list[Project], int]:
    base_stmt = select(Project).where(Project.status != "deleted")
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Project.name).like(normalized_query) | func.lower(Project.description).like(normalized_query)
        )
    stmt = base_stmt.order_by(desc(Project.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def list_active_projects_for_user(
    session: Session,
    *,
    user_id: uuid.UUID,
    limit: int = 100,
    offset: int = 0,
    query: str | None = None,
) -> tuple[list[Project], int]:
    base_stmt = (
        select(Project)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(
            ProjectMember.user_id == user_id,
            Project.status != "deleted",
        )
    )
    if isinstance(query, str) and query.strip():
        normalized_query = f"%{query.strip().lower()}%"
        base_stmt = base_stmt.where(
            func.lower(Project.name).like(normalized_query) | func.lower(Project.description).like(normalized_query)
        )
    stmt = base_stmt.order_by(desc(Project.created_at)).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def get_project_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID) -> ProjectMember | None:
    stmt = select(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id,
    )
    return session.scalar(stmt)


def list_project_members(session: Session, project_id: uuid.UUID) -> list[ProjectMember]:
    stmt = select(ProjectMember).where(ProjectMember.project_id == project_id).order_by(asc(ProjectMember.created_at))
    return list(session.scalars(stmt).all())


def list_user_project_memberships(session: Session, user_id: uuid.UUID) -> list[tuple[ProjectMember, Project]]:
    stmt = (
        select(ProjectMember, Project)
        .join(Project, Project.id == ProjectMember.project_id)
        .where(
            ProjectMember.user_id == user_id,
            Project.status != "deleted",
        )
        .order_by(desc(Project.created_at))
    )
    return list(session.execute(stmt).tuples().all())


def count_project_admins(session: Session, project_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(ProjectMember).where(
        ProjectMember.project_id == project_id,
        ProjectMember.role == "admin",
    )
    return int(session.scalar(stmt) or 0)


def upsert_project_member(session: Session, project_id: uuid.UUID, user_id: uuid.UUID, role: str) -> ProjectMember:
    existing = get_project_member(session, project_id, user_id)
    if existing is None:
        existing = ProjectMember(project_id=project_id, user_id=user_id, role=role)
        session.add(existing)
        session.flush()
        return existing
    existing.role = role
    session.flush()
    return existing


def remove_project_member(session: Session, member: ProjectMember) -> None:
    session.delete(member)
    session.flush()


def get_agent_by_project_and_langgraph_assistant_id(
    session: Session,
    project_id: uuid.UUID,
    langgraph_assistant_id: str,
) -> Agent | None:
    stmt = select(Agent).where(
        Agent.project_id == project_id,
        Agent.langgraph_assistant_id == langgraph_assistant_id,
    )
    return session.scalar(stmt)


def create_audit_log(
    session: Session,
    request_id: str,
    plane: str,
    method: str,
    path: str,
    query: str,
    status_code: int,
    duration_ms: int,
    project_id: uuid.UUID | None,
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
        project_id=project_id,
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


def list_audit_logs_for_project(
    session: Session,
    project_id: uuid.UUID,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    base_stmt = select(AuditLog).where(AuditLog.project_id == project_id)
    stmt = base_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total


def list_audit_logs(
    session: Session,
    *,
    limit: int,
    offset: int,
) -> tuple[list[AuditLog], int]:
    base_stmt = select(AuditLog)
    stmt = base_stmt.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    count_stmt = select(func.count()).select_from(base_stmt.subquery())
    rows = list(session.scalars(stmt).all())
    total = int(session.scalar(count_stmt) or 0)
    return rows, total
