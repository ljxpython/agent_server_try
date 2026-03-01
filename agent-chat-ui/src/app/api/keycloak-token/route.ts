import { NextResponse } from "next/server";
import { logFrontendServer } from "@/lib/server-logger";

type CachedToken = {
  token: string;
  expiresAt: number;
};

let cachedToken: CachedToken | null = null;

function decodeJwtExp(token: string): number {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT format");
  }

  const payload = parts[1];
  const normalized = payload + "=".repeat((4 - (payload.length % 4)) % 4);
  const decoded = Buffer.from(normalized, "base64url").toString("utf8");
  const obj = JSON.parse(decoded) as { exp?: number };
  if (typeof obj.exp !== "number") {
    throw new Error("JWT exp is missing");
  }
  return obj.exp;
}

function tokenUrl(): string {
  const explicit = process.env.KEYCLOAK_TOKEN_URL;
  if (explicit) return explicit;

  const issuer = process.env.KEYCLOAK_ISSUER;
  if (issuer) {
    return `${issuer.replace(/\/$/, "")}/protocol/openid-connect/token`;
  }

  const baseUrl = process.env.KEYCLOAK_BASE_URL ?? "http://127.0.0.1:18080";
  const realm = process.env.KEYCLOAK_REALM ?? "agent-platform";
  return `${baseUrl.replace(/\/$/, "")}/realms/${realm}/protocol/openid-connect/token`;
}

function canUseCache(): boolean {
  if (!cachedToken) return false;
  const now = Math.floor(Date.now() / 1000);
  return cachedToken.expiresAt > now + 30;
}

export async function GET() {
  await logFrontendServer({
    level: "info",
    event: "keycloak_token_request",
    message: "Keycloak token route called",
  });

  if ((process.env.KEYCLOAK_TOKEN_PROXY_ENABLED ?? "false") !== "true") {
    await logFrontendServer({
      level: "warn",
      event: "keycloak_token_proxy_disabled",
      message: "Token proxy disabled",
    });
    return NextResponse.json(
      { error: "keycloak_token_proxy_disabled" },
      { status: 403 },
    );
  }

  if (canUseCache()) {
    const token = cachedToken;
    await logFrontendServer({
      level: "debug",
      event: "keycloak_token_cache_hit",
      message: "Using cached keycloak token",
      context: {
        expires_at: token?.expiresAt,
      },
    });
    return NextResponse.json({
      access_token: token?.token,
      expires_at: token?.expiresAt,
      cached: true,
    });
  }

  const username = process.env.KEYCLOAK_TOKEN_USERNAME;
  const password = process.env.KEYCLOAK_TOKEN_PASSWORD;
  const clientId = process.env.KEYCLOAK_CLIENT_ID ?? "agent-proxy";

  if (!username || !password) {
    await logFrontendServer({
      level: "error",
      event: "keycloak_token_missing_credentials",
      message: "Missing keycloak token credentials",
    });
    return NextResponse.json(
      {
        error: "missing_keycloak_credentials",
        message:
          "KEYCLOAK_TOKEN_USERNAME and KEYCLOAK_TOKEN_PASSWORD are required",
      },
      { status: 500 },
    );
  }

  const body = new URLSearchParams({
    grant_type: "password",
    client_id: clientId,
    username,
    password,
  });

  const res = await fetch(tokenUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
    cache: "no-store",
  });

  const text = await res.text();
  if (!res.ok) {
    await logFrontendServer({
      level: "error",
      event: "keycloak_token_upstream_error",
      message: "Keycloak token upstream request failed",
      context: {
        status: res.status,
      },
    });
    return NextResponse.json(
      {
        error: "keycloak_token_request_failed",
        status: res.status,
        body: text,
      },
      { status: 502 },
    );
  }

  const payload = JSON.parse(text) as { access_token?: string };
  if (!payload.access_token) {
    await logFrontendServer({
      level: "error",
      event: "keycloak_token_missing_in_response",
      message: "access_token missing in Keycloak response",
    });
    return NextResponse.json(
      {
        error: "keycloak_token_missing",
      },
      { status: 502 },
    );
  }

  const exp = decodeJwtExp(payload.access_token);
  cachedToken = {
    token: payload.access_token,
    expiresAt: exp,
  };

  await logFrontendServer({
    level: "info",
    event: "keycloak_token_issued",
    message: "Fetched new keycloak token",
    context: {
      expires_at: exp,
    },
  });

  return NextResponse.json({
    access_token: payload.access_token,
    expires_at: exp,
    cached: false,
  });
}
