from __future__ import annotations

import csv
from datetime import datetime
from io import StringIO
from typing import Any

from fastapi import HTTPException, Request

from app.db.access import aggregate_audit_logs, list_audit_logs, parse_uuid
from app.db.session import session_scope
from app.services.platform_common import (
    current_user_id_from_request,
    db_session_factory_from_request,
    require_tenant_admin,
    resolve_tenant_or_404,
)


async def query_tenant_audit_logs_data(
    request: Request,
    tenant_ref: str,
    limit: int,
    offset: int,
    plane: str | None,
    method: str | None,
    path_prefix: str | None,
    status_code: int | None,
    user_id: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, Any]:
    acting_user_id = current_user_id_from_request(request)
    filter_user_id = parse_uuid(user_id) if user_id else None
    if user_id and filter_user_id is None:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

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

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "id": str(r.id),
                    "request_id": r.request_id,
                    "plane": r.plane,
                    "method": r.method,
                    "path": r.path,
                    "query": r.query,
                    "status_code": r.status_code,
                    "duration_ms": r.duration_ms,
                    "tenant_id": str(r.tenant_id) if r.tenant_id else None,
                    "user_id": str(r.user_id) if r.user_id else None,
                    "user_subject": r.user_subject,
                    "client_ip": r.client_ip,
                    "created_at": r.created_at,
                }
                for r in rows
            ],
        }


async def query_tenant_audit_stats_data(
    request: Request,
    tenant_ref: str,
    by: str,
    limit: int,
    from_time: datetime | None,
    to_time: datetime | None,
) -> dict[str, Any]:
    acting_user_id = current_user_id_from_request(request)
    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)
        rows = aggregate_audit_logs(
            session,
            tenant_id=tenant.id,
            by=by,
            limit=limit,
            from_time=from_time,
            to_time=to_time,
        )
        return {
            "by": by,
            "items": [{"key": k, "count": c} for k, c in rows],
        }


async def export_tenant_audit_logs_csv(
    request: Request,
    tenant_ref: str,
    plane: str | None,
    method: str | None,
    path_prefix: str | None,
    status_code: int | None,
    user_id: str | None,
    from_time: datetime | None,
    to_time: datetime | None,
    max_rows: int,
) -> tuple[str, str]:
    acting_user_id = current_user_id_from_request(request)
    filter_user_id = parse_uuid(user_id) if user_id else None
    if user_id and filter_user_id is None:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    session_factory = db_session_factory_from_request(request)
    with session_scope(session_factory) as session:
        tenant = resolve_tenant_or_404(session, tenant_ref)
        require_tenant_admin(session, tenant_id=tenant.id, acting_user_id=acting_user_id)

        rows, _ = list_audit_logs(
            session,
            tenant_id=tenant.id,
            limit=max_rows,
            offset=0,
            plane=plane,
            method=method,
            path_prefix=path_prefix,
            status_code=status_code,
            user_id=filter_user_id,
            from_time=from_time,
            to_time=to_time,
        )

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "created_at",
                "request_id",
                "plane",
                "method",
                "path",
                "query",
                "status_code",
                "duration_ms",
                "tenant_id",
                "user_id",
                "user_subject",
                "client_ip",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    str(row.id),
                    row.created_at.isoformat(),
                    row.request_id,
                    row.plane,
                    row.method,
                    row.path,
                    row.query,
                    row.status_code,
                    row.duration_ms,
                    str(row.tenant_id) if row.tenant_id else "",
                    str(row.user_id) if row.user_id else "",
                    row.user_subject or "",
                    row.client_ip or "",
                ]
            )

        csv_text = output.getvalue()
        filename = f"audit_logs_{tenant.id}.csv"
        return csv_text, filename
