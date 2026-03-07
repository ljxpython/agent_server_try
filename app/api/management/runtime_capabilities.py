from __future__ import annotations

from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/runtime", tags=["management-runtime"])



async def _proxy_internal_capabilities(request: Request, path: str) -> Any:
    client: httpx.AsyncClient = request.app.state.client
    base_url: str = request.app.state.settings.langgraph_upstream_url
    url = f"{base_url.rstrip('/')}{path}"

    headers: dict[str, str] = {"accept": "application/json"}
    auth_header = request.headers.get("authorization")
    if auth_header:
        headers["authorization"] = auth_header

    try:
        response = await client.get(url, headers=headers)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"runtime_capabilities_timeout: {exc}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"runtime_capabilities_unavailable: {exc}") from exc

    if response.status_code >= 400:
        try:
            detail: Any = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    try:
        return response.json()
    except Exception:
        return {"raw": response.text}


@router.get("/models")
async def list_runtime_models(request: Request) -> Any:
    return await _proxy_internal_capabilities(request, "/internal/capabilities/models")


@router.get("/tools")
async def list_runtime_tools(request: Request) -> Any:
    return await _proxy_internal_capabilities(request, "/internal/capabilities/tools")
