# LangGraph Transparent Proxy (FastAPI)

This service is a transparent proxy in front of a LangGraph API server.

The goal is full API passthrough so `agent-chat-ui` can point to this service
without changing its request paths.

## Environment variables

- `LANGGRAPH_UPSTREAM_URL` (default: `http://127.0.0.1:8123`)
- `LANGGRAPH_UPSTREAM_API_KEY` (optional, injected as `x-api-key` to upstream)
- `PROXY_TIMEOUT_SECONDS` (default: `300`)
- `PROXY_CORS_ALLOW_ORIGINS` (default: `*`, comma-separated)

## Run

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

## Health check

```bash
curl http://127.0.0.1:2024/_proxy/health
```

## Notes

- All incoming paths and methods are forwarded as-is.
- Status code and response headers are preserved (except hop-by-hop headers).
- SSE and long responses are streamed through directly.

## Docs

- `docs/README.md`
- `docs/platform-plan.md`
- `docs/execution-status.md`
