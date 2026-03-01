from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.platform import router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_list_tenants_sets_total_count_header(monkeypatch):
    async def fake_list_my_tenants(request, limit, offset, sort_by, sort_order):
        return ([{"id": "t1", "name": "Tenant A", "slug": "tenant-a", "status": "active"}], 7)

    monkeypatch.setattr("app.api.platform.list_my_tenants", fake_list_my_tenants)

    with _build_client() as client:
        resp = client.get("/_platform/tenants")

    assert resp.status_code == 200
    assert resp.headers["x-total-count"] == "7"
    assert resp.json() == [{"id": "t1", "name": "Tenant A", "slug": "tenant-a", "status": "active"}]


def test_export_audit_logs_keeps_csv_contract(monkeypatch):
    csv_text = (
        "id,created_at,request_id,plane,method,path,query,status_code,duration_ms,tenant_id,user_id,user_subject,client_ip\n"
        "1,2026-01-01T00:00:00,rid,control_plane,GET,/_platform/tenants,,200,10,t1,u1,sub,127.0.0.1\n"
    )

    async def fake_export(*args, **kwargs):
        return csv_text, "audit_logs_t1.csv"

    monkeypatch.setattr("app.api.platform.export_tenant_audit_logs_csv", fake_export)

    with _build_client() as client:
        resp = client.get("/_platform/tenants/t1/audit-logs/export")

    assert resp.status_code == 200
    assert resp.headers["content-disposition"] == 'attachment; filename="audit_logs_t1.csv"'
    assert resp.text.splitlines()[0] == (
        "id,created_at,request_id,plane,method,path,query,status_code,duration_ms,tenant_id,user_id,user_subject,client_ip"
    )


def test_query_audit_logs_response_shape(monkeypatch):
    async def fake_query(*args, **kwargs):
        return {
            "total": 1,
            "limit": 50,
            "offset": 0,
            "items": [
                {
                    "id": "a1",
                    "request_id": "rid-1",
                    "plane": "control_plane",
                    "method": "GET",
                    "path": "/_platform/tenants",
                    "query": "",
                    "status_code": 200,
                    "duration_ms": 11,
                    "tenant_id": "t1",
                    "user_id": "u1",
                    "user_subject": "s1",
                    "client_ip": "127.0.0.1",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }

    monkeypatch.setattr("app.api.platform.query_tenant_audit_logs_data", fake_query)

    with _build_client() as client:
        resp = client.get("/_platform/tenants/t1/audit-logs")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["path"] == "/_platform/tenants"
