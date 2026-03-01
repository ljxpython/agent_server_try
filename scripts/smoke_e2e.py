from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import uuid

import requests


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _token_url() -> str:
    issuer = os.getenv("KEYCLOAK_ISSUER", "http://127.0.0.1:18080/realms/agent-platform").rstrip("/")
    return f"{issuer}/protocol/openid-connect/token"


def _get_token(username: str, password: str) -> str:
    response = requests.post(
        _token_url(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "password",
            "client_id": "agent-proxy",
            "username": username,
            "password": password,
        },
        timeout=10,
    )
    if response.status_code != 200:
        _fail(f"token request failed for {username}: {response.status_code} {response.text}")
    token = response.json().get("access_token")
    if not token:
        _fail(f"empty access token for {username}")
    return token


def _token_sub(token: str) -> str:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def _wait_health(base_url: str, timeout_seconds: float = 12.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            response = requests.get(f"{base_url}/_proxy/health", timeout=2)
            if response.status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.2)
    _fail("server health check timeout")


def main() -> None:
    port = int(os.getenv("SMOKE_PORT", "2199"))
    base_url = f"http://127.0.0.1:{port}"

    owner_token = _get_token("demo_user", "Demo@123456")
    member_token = _get_token("demo_member", "Demo@123456")
    member_sub = _token_sub(member_token)

    env = os.environ.copy()
    env.setdefault("PLATFORM_DB_ENABLED", "true")
    env.setdefault("KEYCLOAK_AUTH_ENABLED", "true")
    env.setdefault("KEYCLOAK_AUTH_REQUIRED", "true")
    env.setdefault("OPENFGA_ENABLED", "true")
    env.setdefault("OPENFGA_AUTHZ_ENABLED", "true")
    env.setdefault("RUNTIME_ROLE_ENFORCEMENT_ENABLED", "true")

    process = subprocess.Popen(
        ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )

    try:
        _wait_health(base_url)

        preflight_headers = {
            "Origin": "http://localhost:3001",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,x-tenant-id,x-agent-id",
        }
        preflight = requests.options(f"{base_url}/info", headers=preflight_headers, timeout=10)
        if preflight.status_code != 200:
            _fail(f"OPTIONS /info expected 200 got {preflight.status_code}")

        unauthorized = requests.get(
            f"{base_url}/info",
            headers={"Origin": "http://localhost:3001"},
            timeout=10,
        )
        if unauthorized.status_code != 401:
            _fail(f"GET /info without token expected 401 got {unauthorized.status_code}")
        if unauthorized.headers.get("access-control-allow-origin") != "http://localhost:3001":
            _fail("401 response missing CORS allow-origin")

        owner_json_headers = {
            "Authorization": f"Bearer {owner_token}",
            "Content-Type": "application/json",
        }
        owner_headers = {"Authorization": f"Bearer {owner_token}"}
        member_headers = {"Authorization": f"Bearer {member_token}"}

        tenant_slug = f"smoke-{uuid.uuid4().hex[:8]}"
        tenant_response = requests.post(
            f"{base_url}/_platform/tenants",
            headers=owner_json_headers,
            json={"name": f"Tenant {tenant_slug}", "slug": tenant_slug},
            timeout=10,
        )
        if tenant_response.status_code != 200:
            _fail(f"create tenant failed: {tenant_response.status_code} {tenant_response.text}")
        tenant_id = tenant_response.json()["id"]

        add_member = requests.post(
            f"{base_url}/_platform/tenants/{tenant_id}/memberships",
            headers=owner_json_headers,
            json={"external_subject": member_sub, "email": "demo_member@example.com", "role": "member"},
            timeout=10,
        )
        if add_member.status_code != 200:
            _fail(f"add membership failed: {add_member.status_code} {add_member.text}")

        project_response = requests.post(
            f"{base_url}/_platform/projects",
            headers=owner_json_headers,
            json={"tenant_id": tenant_id, "name": "Smoke Project"},
            timeout=10,
        )
        if project_response.status_code != 200:
            _fail(f"create project failed: {project_response.status_code} {project_response.text}")
        project_id = project_response.json()["id"]

        agent_response = requests.post(
            f"{base_url}/_platform/assistants",
            headers=owner_json_headers,
            json={
                "project_id": project_id,
                "name": "Smoke Agent",
                "graph_id": "smoke-graph",
                "runtime_base_url": "http://127.0.0.1:8123",
                "description": "",
            },
            timeout=10,
        )
        if agent_response.status_code != 200:
            _fail(f"create assistant failed: {agent_response.status_code} {agent_response.text}")
        agent_id = agent_response.json()["id"]

        member_read = requests.get(
            f"{base_url}/info",
            headers={**member_headers, "x-tenant-id": tenant_id, "x-agent-id": agent_id},
            timeout=10,
        )
        if member_read.status_code != 200:
            _fail(f"member read runtime failed: {member_read.status_code} {member_read.text}")

        member_write = requests.post(
            f"{base_url}/threads",
            headers={**member_headers, "x-tenant-id": tenant_id, "x-agent-id": agent_id, "Content-Type": "application/json"},
            json={},
            timeout=10,
        )
        if member_write.status_code != 403:
            _fail(f"member write runtime expected 403 got {member_write.status_code}")

        owner_write = requests.post(
            f"{base_url}/threads",
            headers={**owner_headers, "x-tenant-id": tenant_id, "x-agent-id": agent_id, "Content-Type": "application/json"},
            json={},
            timeout=10,
        )
        if owner_write.status_code in {401, 403}:
            _fail(f"owner write runtime denied: {owner_write.status_code} {owner_write.text}")

        remove_member = requests.delete(
            f"{base_url}/_platform/tenants/{tenant_id}/memberships/{member_sub}",
            headers=owner_headers,
            timeout=10,
        )
        if remove_member.status_code != 200:
            _fail(f"remove membership failed: {remove_member.status_code} {remove_member.text}")

        member_after_remove = requests.get(
            f"{base_url}/info",
            headers={**member_headers, "x-tenant-id": tenant_id, "x-agent-id": agent_id},
            timeout=10,
        )
        if member_after_remove.status_code != 403:
            _fail(f"member should be denied after removal, got {member_after_remove.status_code}")

        audit_query = requests.get(
            f"{base_url}/_platform/tenants/{tenant_id}/audit-logs?limit=10",
            headers=owner_headers,
            timeout=10,
        )
        if audit_query.status_code != 200:
            _fail(f"audit query failed: {audit_query.status_code} {audit_query.text}")
        total = int(audit_query.json().get("total", 0))
        if total <= 0:
            _fail("audit query returned empty total")

        print("PASS: smoke_e2e")
    finally:
        process.terminate()
        process.wait(timeout=10)


if __name__ == "__main__":
    main()
