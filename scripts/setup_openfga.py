from __future__ import annotations

import asyncio
import os

from app.auth.openfga import OpenFgaClient, OpenFgaSettings


async def main() -> None:
    settings = OpenFgaSettings(
        enabled=True,
        authz_enabled=False,
        auto_bootstrap=True,
        base_url=os.getenv("OPENFGA_URL", "http://127.0.0.1:18081"),
        store_id=os.getenv("OPENFGA_STORE_ID") or None,
        model_id=os.getenv("OPENFGA_MODEL_ID") or None,
        model_file=os.getenv("OPENFGA_MODEL_FILE", "config/openfga-models/v1.json"),
    )

    client = OpenFgaClient(settings)
    try:
        await client.ensure_ready()
        print(f"OPENFGA_STORE_ID={client.store_id}")
        print(f"OPENFGA_MODEL_ID={client.model_id}")
        print(f"OPENFGA_MODEL_FILE={settings.model_file}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
