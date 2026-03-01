from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from urllib import parse, request
from urllib.error import HTTPError, URLError


def _decode_jwt_exp(token: str) -> int:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("invalid jwt token format")

    payload = parts[1]
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload.encode("utf-8"))
    obj = json.loads(decoded.decode("utf-8"))
    exp = obj.get("exp")
    if not isinstance(exp, int):
        raise ValueError("jwt exp is missing")
    return exp


def _default_token_url() -> str:
    explicit = os.getenv("KEYCLOAK_TOKEN_URL")
    if explicit:
        return explicit

    issuer = os.getenv("KEYCLOAK_ISSUER")
    if issuer:
        return issuer.rstrip("/") + "/protocol/openid-connect/token"

    base_url = os.getenv("KEYCLOAK_BASE_URL", "http://127.0.0.1:18080")
    realm = os.getenv("KEYCLOAK_REALM", "agent-platform")
    return f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token"


def _load_cache(cache_file: Path, skew_seconds: int) -> str | None:
    if not cache_file.exists():
        return None

    try:
        obj = json.loads(cache_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    token = obj.get("access_token")
    expires_at = obj.get("expires_at")
    if not isinstance(token, str) or not isinstance(expires_at, int):
        return None

    now = int(time.time())
    if expires_at <= now + skew_seconds:
        return None
    return token


def _save_cache(cache_file: Path, token: str) -> None:
    exp = _decode_jwt_exp(token)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": token,
        "expires_at": exp,
    }
    cache_file.write_text(json.dumps(payload), encoding="utf-8")


def _fetch_token(token_url: str, client_id: str, username: str, password: str) -> str:
    body = parse.urlencode(
        {
            "grant_type": "password",
            "client_id": client_id,
            "username": username,
            "password": password,
        }
    ).encode("utf-8")

    req = request.Request(
        token_url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"token request failed: http={exc.code} body={detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"token request failed: {exc}") from exc

    token = data.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"token response missing access_token: {data}")
    return token


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and cache Keycloak token for local development"
    )
    parser.add_argument("--token-url", default=_default_token_url())
    parser.add_argument("--client-id", default=os.getenv("KEYCLOAK_CLIENT_ID", "agent-proxy"))
    parser.add_argument("--username", default=os.getenv("KEYCLOAK_TOKEN_USERNAME"))
    parser.add_argument("--password", default=os.getenv("KEYCLOAK_TOKEN_PASSWORD"))
    parser.add_argument(
        "--cache-file",
        default=os.getenv("KEYCLOAK_TOKEN_CACHE_FILE", ".cache/keycloak_token.json"),
    )
    parser.add_argument(
        "--skew-seconds",
        type=int,
        default=int(os.getenv("KEYCLOAK_TOKEN_CACHE_SKEW_SECONDS", "30")),
    )
    parser.add_argument(
        "--auth-header",
        action="store_true",
        help="Output 'Authorization: Bearer <token>'",
    )
    parser.add_argument(
        "--print-exp",
        action="store_true",
        help="Print token expiry timestamp to stderr",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.username or not args.password:
        print(
            "Missing credentials: set KEYCLOAK_TOKEN_USERNAME and KEYCLOAK_TOKEN_PASSWORD",
            file=sys.stderr,
        )
        return 2

    cache_file = Path(args.cache_file)
    token = _load_cache(cache_file, args.skew_seconds)
    if token is None:
        token = _fetch_token(args.token_url, args.client_id, args.username, args.password)
        _save_cache(cache_file, token)

    if args.print_exp:
        print(f"TOKEN_EXP={_decode_jwt_exp(token)}", file=sys.stderr)

    if args.auth_header:
        print(f"Authorization: Bearer {token}")
    else:
        print(token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
