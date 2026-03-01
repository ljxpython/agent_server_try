from __future__ import annotations

from typing import AsyncIterator
import logging

import httpx
from fastapi import Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app.auth.openfga import fga_agent, fga_tenant, fga_user
from app.config import Settings
from app.db.access import get_agent_with_project, parse_uuid
from app.db.session import session_scope


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def _strip_request_headers(headers: dict[str, str]) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in HOP_BY_HOP_HEADERS or lower_key in {"host", "content-length"}:
            continue
        cleaned[key] = value
    return cleaned


def _strip_response_headers(headers: httpx.Headers) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key in HOP_BY_HOP_HEADERS or lower_key == "content-length":
            continue
        cleaned[key] = value
    return cleaned


def _upstream_url(base_url: str, path: str, query: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path.lstrip("/")
    url = f"{normalized_base}/{normalized_path}"
    if query:
        return f"{url}?{query}"
    return url


def _runtime_write_method(method: str) -> bool:
    return method.upper() in {"POST", "PUT", "PATCH", "DELETE"}


def _cors_json_error(request: Request, status_code: int, content: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Vary": "Origin",
        },
    )


def _enforce_tenant_write_policy(
    request: Request,
    settings: Settings,
    logger: logging.Logger,
) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    if not settings.runtime_role_enforcement_enabled:
        return None
    if not getattr(request.state, "tenant_id", None):
        return None
    role = getattr(request.state, "membership_role", None)
    if role == "member" and _runtime_write_method(request.method):
        logger.warning(
            "runtime_policy_denied request_id=%s reason=member_write_block method=%s path=%s",
            request.state.request_id,
            request.method,
            request.url.path,
        )
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "Member role cannot perform runtime write operations",
                "request_id": request.state.request_id,
            },
        )
    return None


def _enforce_agent_mapping(request: Request, logger: logging.Logger) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    tenant_id = getattr(request.state, "tenant_id", None)
    agent_header = request.headers.get("x-agent-id")
    if not agent_header:
        return None

    logger.info(
        "agent_mapping_check request_id=%s tenant_id=%s agent_header=%s",
        request.state.request_id,
        tenant_id,
        agent_header,
    )

    if not tenant_id:
        logger.warning(
            "agent_mapping_invalid request_id=%s reason=missing_tenant_context",
            request.state.request_id,
        )
        return _cors_json_error(
            request,
            400,
            {
                "error": "agent_context_invalid",
                "message": "x-agent-id requires x-tenant-id context",
                "request_id": request.state.request_id,
            },
        )

    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        logger.error(
            "agent_mapping_failed request_id=%s reason=db_session_factory_missing",
            request.state.request_id,
        )
        return _cors_json_error(
            request,
            503,
            {
                "error": "db_misconfigured",
                "message": "Database is required for agent mapping checks",
                "request_id": request.state.request_id,
            },
        )

    agent_uuid = parse_uuid(agent_header)
    if agent_uuid is None:
        logger.warning(
            "agent_mapping_invalid request_id=%s reason=invalid_agent_id raw=%s",
            request.state.request_id,
            agent_header,
        )
        return _cors_json_error(
            request,
            400,
            {
                "error": "agent_context_invalid",
                "message": "Invalid x-agent-id",
                "request_id": request.state.request_id,
            },
        )

    with session_scope(session_factory) as session:
        row = get_agent_with_project(session, agent_uuid)
        if row is None:
            logger.warning(
                "agent_mapping_not_found request_id=%s agent_id=%s",
                request.state.request_id,
                agent_header,
            )
            return _cors_json_error(
                request,
                404,
                {
                    "error": "agent_not_found",
                    "message": "Agent not found",
                    "request_id": request.state.request_id,
                },
            )
        agent, project = row
        if str(project.tenant_id) != str(tenant_id):
            logger.warning(
                "agent_mapping_denied request_id=%s tenant_id=%s project_tenant_id=%s agent_id=%s",
                request.state.request_id,
                tenant_id,
                project.tenant_id,
                agent.id,
            )
            return _cors_json_error(
                request,
                403,
                {
                    "error": "runtime_policy_denied",
                    "message": "Agent does not belong to tenant",
                    "request_id": request.state.request_id,
                },
            )
        request.state.agent_id = str(agent.id)
        logger.info(
            "agent_mapping_ok request_id=%s tenant_id=%s agent_id=%s",
            request.state.request_id,
            tenant_id,
            request.state.agent_id,
        )
    return None


async def _enforce_openfga_runtime_policy(
    request: Request,
    settings: Settings,
    logger: logging.Logger,
) -> JSONResponse | None:
    if request.method.upper() == "OPTIONS":
        return None
    if not settings.openfga_authz_enabled:
        return None
    if not getattr(request.state, "tenant_id", None):
        return None

    openfga_client = getattr(request.app.state, "openfga_client", None)
    user_subject = getattr(request.state, "user_subject", None)
    if openfga_client is None or not user_subject:
        logger.warning(
            "openfga_context_incomplete request_id=%s tenant_id=%s user_subject=%s",
            request.state.request_id,
            request.state.tenant_id,
            user_subject,
        )
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "OpenFGA authorization context is incomplete",
                "request_id": request.state.request_id,
            },
        )

    relation = "can_write" if _runtime_write_method(request.method) else "can_read"

    tenant_allowed = await openfga_client.check(
        user=fga_user(str(user_subject)),
        relation=relation,
        obj=fga_tenant(str(request.state.tenant_id)),
    )
    if not tenant_allowed:
        logger.warning(
            "openfga_denied request_id=%s level=tenant relation=%s tenant_id=%s user_subject=%s",
            request.state.request_id,
            relation,
            request.state.tenant_id,
            user_subject,
        )
        return _cors_json_error(
            request,
            403,
            {
                "error": "runtime_policy_denied",
                "message": "OpenFGA denied access to tenant runtime",
                "request_id": request.state.request_id,
            },
        )

    agent_id = getattr(request.state, "agent_id", None)
    if agent_id:
        agent_allowed = await openfga_client.check(
            user=fga_user(str(user_subject)),
            relation=relation,
            obj=fga_agent(str(agent_id)),
        )
        if not agent_allowed:
            logger.warning(
                "openfga_denied request_id=%s level=agent relation=%s agent_id=%s user_subject=%s",
                request.state.request_id,
                relation,
                agent_id,
                user_subject,
            )
            return _cors_json_error(
                request,
                403,
                {
                    "error": "runtime_policy_denied",
                    "message": "OpenFGA denied access to agent runtime",
                    "request_id": request.state.request_id,
                },
            )

    return None


async def passthrough_request(
    request: Request,
    full_path: str,
    settings: Settings,
    logger: logging.Logger,
) -> Response:
    upstream_base_url = settings.langgraph_upstream_url
    upstream_api_key = settings.langgraph_upstream_api_key
    upstream_url = _upstream_url(upstream_base_url, full_path, request.url.query)
    logger.info(
        "passthrough_prepare request_id=%s method=%s upstream=%s",
        request.state.request_id,
        request.method,
        upstream_url,
    )

    violation = _enforce_tenant_write_policy(request, settings, logger)
    if violation is not None:
        return violation

    violation = _enforce_agent_mapping(request, logger)
    if violation is not None:
        return violation

    violation = await _enforce_openfga_runtime_policy(request, settings, logger)
    if violation is not None:
        return violation

    headers = _strip_request_headers(dict(request.headers))
    headers["x-request-id"] = request.state.request_id
    if upstream_api_key:
        headers["x-api-key"] = upstream_api_key

    body = await request.body()
    logger.debug(
        "passthrough_payload request_id=%s body_size=%s has_upstream_api_key=%s",
        request.state.request_id,
        len(body),
        bool(upstream_api_key),
    )

    retries = settings.proxy_upstream_retries
    attempt = 0
    upstream_response = None

    while attempt <= retries:
        try:
            upstream_request = request.app.state.client.build_request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
            )
            upstream_response = await request.app.state.client.send(upstream_request, stream=True)
            break
        except httpx.TimeoutException as exc:
            if attempt < retries:
                logger.warning(
                    "upstream_timeout_retry request_id=%s attempt=%s/%s error=%s",
                    request.state.request_id,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                attempt += 1
                continue
            return _cors_json_error(
                request,
                504,
                {
                    "error": "gateway_timeout",
                    "message": f"Upstream timeout: {exc}",
                    "request_id": request.state.request_id,
                },
            )
        except httpx.HTTPError as exc:
            if attempt < retries:
                logger.warning(
                    "upstream_http_retry request_id=%s attempt=%s/%s error=%s",
                    request.state.request_id,
                    attempt + 1,
                    retries + 1,
                    exc,
                )
                attempt += 1
                continue
            return _cors_json_error(
                request,
                502,
                {
                    "error": "bad_gateway",
                    "message": f"Failed to reach upstream: {exc}",
                    "request_id": request.state.request_id,
                },
            )

    if upstream_response is None:
        return _cors_json_error(
            request,
            502,
            {
                "error": "bad_gateway",
                "message": "Failed to reach upstream",
                "request_id": request.state.request_id,
            },
        )

    response_headers = _strip_response_headers(upstream_response.headers)
    logger.info(
        "passthrough_upstream_response request_id=%s status=%s content_type=%s",
        request.state.request_id,
        upstream_response.status_code,
        upstream_response.headers.get("content-type"),
    )

    async def stream_body() -> AsyncIterator[bytes]:
        try:
            async for chunk in upstream_response.aiter_raw():
                if chunk:
                    yield chunk
        finally:
            await upstream_response.aclose()

    return StreamingResponse(
        stream_body(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=upstream_response.headers.get("content-type"),
    )
