from __future__ import annotations

import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator
import logging

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from dotenv import load_dotenv


load_dotenv()

logger = logging.getLogger("proxy")
logging.basicConfig(
    level=os.getenv("PROXY_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


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


def _request_id(request: Request) -> str:
    incoming = request.headers.get("x-request-id")
    if incoming:
        return incoming
    return uuid.uuid4().hex


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    timeout_seconds = float(os.getenv("PROXY_TIMEOUT_SECONDS", "300"))
    timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=timeout_seconds, pool=5.0)
    app.state.client = httpx.AsyncClient(timeout=timeout)
    try:
        yield
    finally:
        await app.state.client.aclose()


app = FastAPI(
    title="LangGraph Transparent Proxy",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("PROXY_CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    started = time.perf_counter()
    request_id = _request_id(request)
    request.state.request_id = request_id

    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.exception(
            "request_failed request_id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            elapsed_ms,
        )
        raise

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    response.headers["x-request-id"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.get("/_proxy/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.api_route(
    "/{full_path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
)
async def passthrough(request: Request, full_path: str) -> Response:
    upstream_base_url = os.getenv("LANGGRAPH_UPSTREAM_URL", "http://127.0.0.1:8123")
    upstream_api_key = os.getenv("LANGGRAPH_UPSTREAM_API_KEY")
    upstream_url = _upstream_url(upstream_base_url, full_path, request.url.query)

    headers = _strip_request_headers(dict(request.headers))
    headers["x-request-id"] = request.state.request_id
    if upstream_api_key:
        headers["x-api-key"] = upstream_api_key

    body = await request.body()

    retries = max(0, int(os.getenv("PROXY_UPSTREAM_RETRIES", "1")))
    attempt = 0
    upstream_response = None

    while attempt <= retries:
        try:
            upstream_request = app.state.client.build_request(
                method=request.method,
                url=upstream_url,
                headers=headers,
                content=body,
            )
            upstream_response = await app.state.client.send(upstream_request, stream=True)
            break
        except httpx.TimeoutException as exc:
            if attempt < retries:
                attempt += 1
                continue
            return JSONResponse(
                status_code=504,
                content={
                    "error": "gateway_timeout",
                    "message": f"Upstream timeout: {exc}",
                    "request_id": request.state.request_id,
                },
            )
        except httpx.HTTPError as exc:
            if attempt < retries:
                attempt += 1
                continue
            return JSONResponse(
                status_code=502,
                content={
                    "error": "bad_gateway",
                    "message": f"Failed to reach upstream: {exc}",
                    "request_id": request.state.request_id,
                },
            )

    if upstream_response is None:
        return JSONResponse(
            status_code=502,
            content={
                "error": "bad_gateway",
                "message": "Failed to reach upstream",
                "request_id": request.state.request_id,
            },
        )

    response_headers = _strip_response_headers(upstream_response.headers)

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
