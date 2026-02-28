from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import jwt
from jwt import InvalidTokenError, PyJWKClient


@dataclass(frozen=True)
class KeycloakSettings:
    enabled: bool
    required: bool
    issuer: str | None
    audience: str | None
    jwks_url: str | None
    cache_ttl_seconds: int


class KeycloakVerifier:
    def __init__(self, settings: KeycloakSettings) -> None:
        if not settings.issuer:
            raise RuntimeError("KEYCLOAK_ISSUER is required when KEYCLOAK_AUTH_ENABLED=true")

        jwks_url = settings.jwks_url
        if not jwks_url:
            issuer = settings.issuer.rstrip("/")
            jwks_url = f"{issuer}/protocol/openid-connect/certs"

        self.settings = settings
        self.jwks_url = jwks_url
        self._jwks_client = PyJWKClient(jwks_url)
        self._last_refresh = 0.0

    def _refresh_keyset_if_needed(self) -> None:
        now = time.time()
        if now - self._last_refresh < self.settings.cache_ttl_seconds:
            return
        self._jwks_client = PyJWKClient(self.jwks_url)
        self._last_refresh = now

    def verify_token(self, token: str) -> dict[str, Any]:
        self._refresh_keyset_if_needed()

        signing_key = self._jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256", "RS384", "RS512"],
            audience=self.settings.audience,
            issuer=self.settings.issuer,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_iss": bool(self.settings.issuer),
                "verify_aud": bool(self.settings.audience),
                "require": ["exp", "iat", "sub"],
            },
        )
        return payload


def extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def is_invalid_token_error(exc: Exception) -> bool:
    return isinstance(exc, InvalidTokenError)
