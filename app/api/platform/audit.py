from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from app.services.platform_service import (
    export_tenant_audit_logs_csv,
    query_tenant_audit_logs_data,
    query_tenant_audit_stats_data,
)

from .common import logger, request_id
from .schemas import AuditLogListResponse, AuditStatsResponse


router = APIRouter()


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
    """查询租户审计日志明细，支持分页与多维过滤。"""
    logger.info(
        "platform_query_audit_logs request_id=%s tenant_ref=%s limit=%s offset=%s",
        request_id(request),
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
    """查询租户审计日志聚合统计。"""
    logger.info(
        "platform_query_audit_stats request_id=%s tenant_ref=%s by=%s limit=%s",
        request_id(request),
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
    """导出租户审计日志为 CSV。"""
    logger.info(
        "platform_export_audit_logs request_id=%s tenant_ref=%s max_rows=%s",
        request_id(request),
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
