from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.services.langgraph_sdk.assistants_service import LangGraphAssistantsService
from app.services.langgraph_sdk.scope_guard import inject_project_metadata


class LangGraphGraphsService:
    _FILTER_FIELDS = (
        "metadata",
        "name",
    )

    def __init__(self, request: Request) -> None:
        self._request = request
        self._assistants_service = LangGraphAssistantsService(request)

    async def search(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_payload = payload if isinstance(payload, dict) else {}
        limit = self._as_non_negative_int(normalized_payload.get("limit"), default=50)
        offset = self._as_non_negative_int(normalized_payload.get("offset"), default=0)
        query = self._as_string(normalized_payload.get("query")).strip().lower()
        sort_order = self._as_string(normalized_payload.get("sort_order")).strip().lower() or "asc"
        if sort_order not in {"asc", "desc"}:
            sort_order = "asc"

        graph_ids = await self._collect_graph_ids(normalized_payload)
        if query:
            graph_ids = [graph_id for graph_id in graph_ids if query in graph_id.lower()]

        reverse = sort_order == "desc"
        graph_ids.sort(reverse=reverse)

        total = len(graph_ids)
        paginated_items = graph_ids[offset : offset + limit]
        return {
            "items": [{"graph_id": graph_id} for graph_id in paginated_items],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def count(self, payload: dict[str, Any]) -> dict[str, int]:
        normalized_payload = payload if isinstance(payload, dict) else {}
        query = self._as_string(normalized_payload.get("query")).strip().lower()
        graph_ids = await self._collect_graph_ids(normalized_payload)
        if query:
            graph_ids = [graph_id for graph_id in graph_ids if query in graph_id.lower()]
        return {"count": len(graph_ids)}

    async def _collect_graph_ids(self, payload: dict[str, Any]) -> list[str]:
        assistants_payload: dict[str, Any] = {
            key: payload[key]
            for key in self._FILTER_FIELDS
            if key in payload and payload[key] is not None
        }
        assistants_payload = inject_project_metadata(self._request, assistants_payload)
        assistants_payload["select"] = ["graph_id"]

        max_assistants = self._as_non_negative_int(payload.get("max_assistants"), default=2000)
        page_size = self._as_non_negative_int(payload.get("assistants_page_size"), default=200)
        if page_size <= 0:
            page_size = 200
        if max_assistants <= 0:
            return []

        unique_graph_ids: set[str] = set()
        fetched = 0
        offset = 0

        while fetched < max_assistants:
            page_payload = {
                **assistants_payload,
                "limit": min(page_size, max_assistants - fetched),
                "offset": offset,
            }
            try:
                rows = await self._assistants_service.search(page_payload)
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail="langgraph_upstream_unavailable") from exc
            assistants = self._extract_assistant_rows(rows)
            if not assistants:
                break

            for assistant in assistants:
                graph_id = assistant.get("graph_id")
                if isinstance(graph_id, str) and graph_id:
                    unique_graph_ids.add(graph_id)

            fetched += len(assistants)
            offset += len(assistants)
            if len(assistants) < page_payload["limit"]:
                break

        return list(unique_graph_ids)

    @staticmethod
    def _extract_assistant_rows(rows: Any) -> list[dict[str, Any]]:
        if isinstance(rows, list):
            return [item for item in rows if isinstance(item, dict)]

        if isinstance(rows, dict):
            items = rows.get("items")
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]

        return []

    @staticmethod
    def _as_non_negative_int(value: Any, *, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return default

    @staticmethod
    def _as_string(value: Any) -> str:
        return value if isinstance(value, str) else ""
