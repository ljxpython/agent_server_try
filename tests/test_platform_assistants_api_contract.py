from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.platform import router  # noqa: E402


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_assistant_includes_langgraph_assistant_id(monkeypatch) -> None:
    # Given the create service returns a LangGraph assistant mapping id.
    async def fake_create_agent_for_project(*args, **kwargs):
        return {
            "id": "assistant-1",
            "project_id": "project-1",
            "name": "Assistant A",
            "graph_id": "assistant",
            "runtime_base_url": "http://runtime.local",
            "langgraph_assistant_id": "lg-assistant-1",
            "description": "contract test",
        }

    monkeypatch.setattr("app.api.platform.assistants.create_agent_for_project", fake_create_agent_for_project)

    payload = {
        "project_id": "project-1",
        "name": "Assistant A",
        "graph_id": "assistant",
        "runtime_base_url": "http://runtime.local",
        "langgraph_assistant_id": "lg-assistant-1",
        "description": "contract test",
    }
    # When posting a valid assistant create payload.
    with _build_client() as client:
        resp = client.post("/_platform/assistants", json=payload)

    # Then response contract includes langgraph_assistant_id.
    assert resp.status_code == 200
    body = resp.json()
    assert body["langgraph_assistant_id"] == "lg-assistant-1"
    assert set(body.keys()) == {
        "id",
        "project_id",
        "name",
        "graph_id",
        "runtime_base_url",
        "langgraph_assistant_id",
        "description",
    }


def test_list_assistants_includes_langgraph_assistant_id_and_total_count(monkeypatch) -> None:
    # Given list service returns rows and total count.
    async def fake_list_agents_for_project_id(request, project_id, limit, offset, sort_by, sort_order):
        return (
            [
                {
                    "id": "assistant-1",
                    "project_id": "project-1",
                    "name": "Assistant A",
                    "graph_id": "assistant",
                    "runtime_base_url": "http://runtime.local",
                    "langgraph_assistant_id": "lg-assistant-1",
                    "description": "contract test",
                }
            ],
            3,
        )

    monkeypatch.setattr("app.api.platform.assistants.list_agents_for_project_id", fake_list_agents_for_project_id)

    # When requesting assistants for a project.
    with _build_client() as client:
        resp = client.get("/_platform/projects/project-1/assistants")

    # Then API returns x-total-count and item mapping ids.
    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "3"
    body = resp.json()
    assert isinstance(body, list)
    assert body
    assert body[0]["langgraph_assistant_id"] == "lg-assistant-1"


def test_update_assistant_preserves_langgraph_assistant_id(monkeypatch) -> None:
    # Given update service returns assistant with a LangGraph id.
    async def fake_update_agent_by_id(*args, **kwargs):
        return {
            "id": "assistant-1",
            "project_id": "project-1",
            "name": "Assistant Updated",
            "graph_id": "assistant",
            "runtime_base_url": "http://runtime.updated",
            "langgraph_assistant_id": "lg-assistant-1",
            "description": "updated",
        }

    monkeypatch.setattr("app.api.platform.assistants.update_agent_by_id", fake_update_agent_by_id)

    payload = {
        "name": "Assistant Updated",
        "graph_id": "assistant",
        "runtime_base_url": "http://runtime.updated",
        "langgraph_assistant_id": "lg-assistant-1",
        "description": "updated",
    }
    # When patching assistant profile fields.
    with _build_client() as client:
        resp = client.patch("/_platform/assistants/assistant-1", json=payload)

    # Then response preserves langgraph_assistant_id.
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "assistant-1"
    assert body["langgraph_assistant_id"] == "lg-assistant-1"
