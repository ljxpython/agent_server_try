from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx


logger = logging.getLogger("proxy.openfga")


@dataclass(frozen=True)
class OpenFgaSettings:
    enabled: bool
    authz_enabled: bool
    auto_bootstrap: bool
    base_url: str
    store_id: str | None
    model_id: str | None
    model_file: str


class OpenFgaClient:
    def __init__(self, settings: OpenFgaSettings, timeout_seconds: float = 10.0) -> None:
        self.settings = settings
        self.base_url = settings.base_url.rstrip("/")
        self.store_id = settings.store_id
        self.model_id = settings.model_id
        self._client = httpx.AsyncClient(timeout=timeout_seconds)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ensure_ready(self) -> None:
        if not self.settings.enabled:
            return
        if self.settings.auto_bootstrap:
            await self.bootstrap_from_file(Path(self.settings.model_file))
        if not self.store_id or not self.model_id:
            logger.error("openfga_not_configured store_id=%s model_id=%s", self.store_id, self.model_id)
            raise RuntimeError("OpenFGA store/model is not configured")

    async def bootstrap_from_file(self, model_file: Path) -> None:
        if not model_file.exists():
            logger.error("openfga_model_file_missing file=%s", model_file)
            raise RuntimeError(f"OpenFGA model file not found: {model_file}")

        model_payload = json.loads(model_file.read_text())

        if self.store_id is None:
            store_name = "agent-platform-store"
            created = await self._client.post(
                f"{self.base_url}/stores",
                json={"name": store_name},
            )
            if created.status_code not in {200, 201}:
                logger.error("openfga_create_store_failed status=%s body=%s", created.status_code, created.text)
                raise RuntimeError(f"OpenFGA create store failed: {created.status_code} {created.text}")
            self.store_id = created.json()["id"]
            logger.info("openfga_store_created store_id=%s", self.store_id)

        write_model = await self._client.post(
            f"{self.base_url}/stores/{self.store_id}/authorization-models",
            json=model_payload,
        )
        if write_model.status_code not in {200, 201}:
            logger.error(
                "openfga_write_model_failed status=%s body=%s store_id=%s",
                write_model.status_code,
                write_model.text,
                self.store_id,
            )
            raise RuntimeError(
                f"OpenFGA write model failed: {write_model.status_code} {write_model.text}"
            )
        self.model_id = write_model.json()["authorization_model_id"]
        logger.info("openfga_model_written store_id=%s model_id=%s", self.store_id, self.model_id)

    async def write_tuple(self, user: str, relation: str, obj: str) -> None:
        await self.write_tuples([
            {"user": user, "relation": relation, "object": obj},
        ])

    async def write_tuples(self, tuples: list[dict[str, str]]) -> None:
        if not tuples:
            return
        if not self.store_id or not self.model_id:
            return

        payload = {
            "authorization_model_id": self.model_id,
            "writes": {"tuple_keys": tuples},
        }
        response = await self._client.post(
            f"{self.base_url}/stores/{self.store_id}/write",
            json=payload,
        )
        if response.status_code not in {200, 201}:
            logger.error(
                "openfga_write_tuple_failed status=%s tuple_count=%s body=%s",
                response.status_code,
                len(tuples),
                response.text,
            )
            raise RuntimeError(f"OpenFGA write tuple failed: {response.status_code} {response.text}")

    async def delete_tuples(self, tuples: list[dict[str, str]]) -> None:
        if not tuples:
            return
        if not self.store_id or not self.model_id:
            return

        payload = {
            "authorization_model_id": self.model_id,
            "deletes": {"tuple_keys": tuples},
        }
        response = await self._client.post(
            f"{self.base_url}/stores/{self.store_id}/write",
            json=payload,
        )
        if response.status_code in {200, 201}:
            return
        if response.status_code == 400 and "tuple to be deleted did not exist" in response.text:
            return
        logger.error(
            "openfga_delete_tuple_failed status=%s tuple_count=%s body=%s",
            response.status_code,
            len(tuples),
            response.text,
        )
        raise RuntimeError(f"OpenFGA delete tuple failed: {response.status_code} {response.text}")

    async def delete_tuple(self, user: str, relation: str, obj: str) -> None:
        await self.delete_tuples([
            {"user": user, "relation": relation, "object": obj},
        ])

    async def check(self, user: str, relation: str, obj: str) -> bool:
        if not self.store_id or not self.model_id:
            return False

        payload = {
            "authorization_model_id": self.model_id,
            "tuple_key": {
                "user": user,
                "relation": relation,
                "object": obj,
            },
        }
        response = await self._client.post(
            f"{self.base_url}/stores/{self.store_id}/check",
            json=payload,
        )
        if response.status_code != 200:
            logger.error(
                "openfga_check_failed status=%s user=%s relation=%s object=%s body=%s",
                response.status_code,
                user,
                relation,
                obj,
                response.text,
            )
            raise RuntimeError(f"OpenFGA check failed: {response.status_code} {response.text}")
        return bool(response.json().get("allowed", False))


def fga_user(subject: str) -> str:
    return f"user:{subject}"


def fga_tenant(tenant_id: str) -> str:
    return f"tenant:{tenant_id}"


def fga_project(project_id: str) -> str:
    return f"project:{project_id}"


def fga_agent(agent_id: str) -> str:
    return f"agent:{agent_id}"
