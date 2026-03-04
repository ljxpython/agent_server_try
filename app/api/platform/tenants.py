from __future__ import annotations

from fastapi import APIRouter, Query, Request, Response

from app.services.platform_service import (
    add_membership_to_tenant,
    create_tenant_for_current_user,
    delete_tenant_by_ref,
    list_memberships_for_tenant_ref,
    list_my_tenants,
    remove_membership_from_tenant,
)

from .common import logger, request_id
from .schemas import (
    AddMembershipRequest,
    CreateTenantRequest,
    DeleteTenantResponse,
    DeleteMembershipResponse,
    MembershipListItemResponse,
    MembershipResponse,
    TenantResponse,
)


router = APIRouter()


@router.get("/tenants", response_model=list[TenantResponse])
async def list_my_tenants_endpoint(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="created_at", pattern="^(created_at|name)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
):
    """列出当前用户可见的租户。

    参数说明：
    - request: 请求上下文，用于读取用户身份与请求链路信息。
    - response: 用于写回分页总数响应头 `x-total-count`。
    - limit/offset: 分页参数。
    - sort_by/sort_order: 排序字段与方向。

    返回语义：
    - 返回租户列表。
    - 通过响应头 `x-total-count` 返回总数，便于前端分页。
    """
    logger.info(
        "platform_list_tenants request_id=%s limit=%s offset=%s sort_by=%s sort_order=%s",
        request_id(request),
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
    """为当前用户创建租户。

    参数说明：
    - request: 请求上下文，用于识别操作者。
    - payload: 创建参数（租户名称与可选 slug）。

    返回语义：
    - 返回新建租户对象。
    """
    logger.info(
        "platform_create_tenant request_id=%s name=%s slug=%s",
        request_id(request),
        payload.name,
        payload.slug,
    )
    row = await create_tenant_for_current_user(request, payload.name, payload.slug)
    return TenantResponse(**row)


@router.delete("/tenants/{tenant_ref}", response_model=DeleteTenantResponse)
async def delete_tenant_endpoint(request: Request, tenant_ref: str):
    logger.info(
        "platform_delete_tenant request_id=%s tenant_ref=%s",
        request_id(request),
        tenant_ref,
    )
    row = await delete_tenant_by_ref(request, tenant_ref)
    tenant_id = row.get("tenant_id")
    deleted = row.get("deleted")
    return DeleteTenantResponse(
        tenant_id=tenant_id if isinstance(tenant_id, str) else "",
        deleted=deleted if isinstance(deleted, bool) else False,
    )


@router.post("/tenants/{tenant_ref}/memberships", response_model=MembershipResponse)
async def add_membership(request: Request, tenant_ref: str, payload: AddMembershipRequest):
    """为租户添加或更新成员关系。

    参数说明：
    - request: 请求上下文，用于权限校验。
    - tenant_ref: 租户引用（可为租户 id 或 slug）。
    - payload: 成员标识与角色（owner/admin/member）。

    返回语义：
    - 返回最终生效的 membership 记录。
    """
    logger.info(
        "platform_add_membership request_id=%s tenant_ref=%s role=%s user_id=%s external_subject=%s",
        request_id(request),
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


@router.get("/tenants/{tenant_ref}/memberships", response_model=list[MembershipListItemResponse])
async def list_memberships(
    request: Request,
    response: Response,
    tenant_ref: str,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    logger.info(
        "platform_list_memberships request_id=%s tenant_ref=%s limit=%s offset=%s",
        request_id(request),
        tenant_ref,
        limit,
        offset,
    )
    rows, total = await list_memberships_for_tenant_ref(request, tenant_ref, limit, offset)
    response.headers["x-total-count"] = str(total)
    return [MembershipListItemResponse(**row) for row in rows]


@router.delete("/tenants/{tenant_ref}/memberships/{user_ref}", response_model=DeleteMembershipResponse)
async def remove_membership(request: Request, tenant_ref: str, user_ref: str):
    """移除租户成员关系。

    参数说明：
    - request: 请求上下文，用于权限校验。
    - tenant_ref: 租户引用（id 或 slug）。
    - user_ref: 用户引用（通常为 user id）。

    返回语义：
    - 返回删除结果，含 `deleted` 标记。
    """
    logger.info(
        "platform_remove_membership request_id=%s tenant_ref=%s user_ref=%s",
        request_id(request),
        tenant_ref,
        user_ref,
    )
    row = await remove_membership_from_tenant(request, tenant_ref, user_ref)
    return DeleteMembershipResponse(**row)
