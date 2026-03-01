import { NextResponse } from "next/server";

import { logFrontendServer } from "@/lib/server-logger";

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

export const runtime = "nodejs";

export async function POST(request: Request) {
  try {
    const body = (await request.json()) as {
      code?: string;
      code_verifier?: string;
      redirect_uri?: string;
    };

    if (!body.code || !body.code_verifier || !body.redirect_uri) {
      return NextResponse.json(
        { error: "invalid_request", message: "code/code_verifier/redirect_uri are required" },
        { status: 400 },
      );
    }

    const clientId = process.env.KEYCLOAK_CLIENT_ID ?? "agent-proxy";
    const payload = new URLSearchParams({
      grant_type: "authorization_code",
      client_id: clientId,
      code: body.code,
      code_verifier: body.code_verifier,
      redirect_uri: body.redirect_uri,
    });

    const response = await fetch(tokenUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: payload,
      cache: "no-store",
    });

    const text = await response.text();
    if (!response.ok) {
      await logFrontendServer({
        level: "error",
        event: "oidc_token_exchange_failed",
        message: "OIDC token exchange failed",
        context: {
          status: response.status,
          body: text,
        },
      });
      return NextResponse.json(
        { error: "token_exchange_failed", status: response.status, body: text },
        { status: 502 },
      );
    }

    const tokenSet = JSON.parse(text) as {
      access_token?: string;
      refresh_token?: string;
      id_token?: string;
      expires_in?: number;
    };
    if (!tokenSet.access_token) {
      return NextResponse.json(
        { error: "missing_access_token", body: tokenSet },
        { status: 502 },
      );
    }

    await logFrontendServer({
      level: "info",
      event: "oidc_token_exchange_ok",
      message: "OIDC token exchange succeeded",
    });

    return NextResponse.json({
      access_token: tokenSet.access_token,
      refresh_token: tokenSet.refresh_token,
      id_token: tokenSet.id_token,
      expires_in: tokenSet.expires_in,
    });
  } catch (error) {
    await logFrontendServer({
      level: "error",
      event: "oidc_token_exchange_exception",
      message: "OIDC token exchange exception",
      context: {
        error: String(error),
      },
    });
    return NextResponse.json({ error: "internal_error" }, { status: 500 });
  }
}
