from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

from app.auth.openfga import OpenFgaClient, OpenFgaSettings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default=os.getenv("OPENFGA_URL", "http://127.0.0.1:18081"))
    parser.add_argument("--store-id", default=os.getenv("OPENFGA_STORE_ID"))
    parser.add_argument("--model-id", default=os.getenv("OPENFGA_MODEL_ID"))
    parser.add_argument("--model-file", default=os.getenv("OPENFGA_MODEL_FILE", "config/openfga-models/v1.json"))
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    settings = OpenFgaSettings(
        enabled=True,
        authz_enabled=False,
        auto_bootstrap=False,
        base_url=args.base_url,
        store_id=args.store_id,
        model_id=args.model_id,
        model_file=args.model_file,
    )
    client = OpenFgaClient(settings)
    try:
        if args.apply:
            await client.bootstrap_from_file(Path(args.model_file))
        print(f"OPENFGA_STORE_ID={client.store_id}")
        print(f"OPENFGA_MODEL_ID={client.model_id}")
        print(f"OPENFGA_MODEL_FILE={args.model_file}")
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(run())
