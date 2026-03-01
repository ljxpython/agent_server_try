from __future__ import annotations

import argparse
import os
from pathlib import Path

import httpx


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rollback to a previous OpenFGA authorization model id"
    )
    parser.add_argument("--base-url", default=os.getenv("OPENFGA_URL", "http://127.0.0.1:18081"))
    parser.add_argument("--store-id", default=os.getenv("OPENFGA_STORE_ID"), required=False)
    parser.add_argument("--model-id", required=True, help="Target authorization model id")
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Env file path to update OPENFGA_MODEL_ID",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to env file. Without this flag, performs dry run only.",
    )
    return parser.parse_args()


def _replace_or_append(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.startswith(prefix):
            out.append(f"{prefix}{value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{prefix}{value}")
    return out


def verify_model_exists(base_url: str, store_id: str, model_id: str) -> None:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(
            f"{base_url.rstrip('/')}/stores/{store_id}/authorization-models/{model_id}"
        )
    if resp.status_code != 200:
        raise RuntimeError(
            f"OpenFGA model not found or inaccessible: status={resp.status_code} body={resp.text}"
        )


def run() -> None:
    args = parse_args()
    if not args.store_id:
        raise RuntimeError("OPENFGA_STORE_ID or --store-id is required")

    verify_model_exists(args.base_url, args.store_id, args.model_id)
    print("Verified model exists:", args.model_id)

    env_path = Path(args.env_file)
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    next_lines = _replace_or_append(lines, "OPENFGA_MODEL_ID", args.model_id)

    print(f"OPENFGA_STORE_ID={args.store_id}")
    print(f"OPENFGA_MODEL_ID={args.model_id}")
    print(f"ENV_FILE={env_path}")

    if not args.apply:
        print("Dry run complete. Re-run with --apply to update env file.")
        return

    env_path.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    print("Applied OPENFGA_MODEL_ID update to env file.")


if __name__ == "__main__":
    run()
