"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { consumePkceSession } from "@/lib/oidc-client";
import { ensureApiUrlSeeded, setOidcTokenSet } from "@/lib/oidc-storage";

function OidcCallbackContent() {
  const router = useRouter();
  const params = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      const code = params.get("code");
      const state = params.get("state");
      if (!code || !state) {
        setError("Missing code/state in callback URL.");
        return;
      }

      const session = consumePkceSession();
      if (!session.state || !session.verifier) {
        setError("PKCE session not found. Please login again.");
        return;
      }

      if (session.state !== state) {
        setError("OIDC state mismatch.");
        return;
      }

      const redirectUri = `${window.location.origin}/auth/callback`;
      const response = await fetch("/api/auth/oidc/token", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          code,
          code_verifier: session.verifier,
          redirect_uri: redirectUri,
        }),
      });

      const payload = (await response.json()) as {
        access_token?: string;
        refresh_token?: string;
        id_token?: string;
        expires_in?: number;
        message?: string;
      };

      if (!response.ok || !payload.access_token) {
        setError(payload.message ?? "Token exchange failed.");
        return;
      }

      const expiresAt =
        typeof payload.expires_in === "number"
          ? Math.floor(Date.now() / 1000) + payload.expires_in
          : undefined;

      setOidcTokenSet({
        access_token: payload.access_token,
        refresh_token: payload.refresh_token,
        id_token: payload.id_token,
        expires_at: expiresAt,
      });
      ensureApiUrlSeeded();

      if (!cancelled) {
        router.replace(session.returnTo || "/workspace/chat");
      }
    }

    run().catch((e) => {
      setError(String(e));
    });

    return () => {
      cancelled = true;
    };
  }, [params, router]);

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-3 p-6 text-center">
      <h1 className="text-xl font-semibold">Completing sign in...</h1>
      {error ? <p className="text-sm text-red-600">{error}</p> : <p className="text-muted-foreground text-sm">Please wait.</p>}
    </section>
  );
}

export default function OidcCallbackPage() {
  return (
    <Suspense
      fallback={
        <section className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-3 p-6 text-center">
          <h1 className="text-xl font-semibold">Completing sign in...</h1>
          <p className="text-muted-foreground text-sm">Please wait.</p>
        </section>
      }
    >
      <OidcCallbackContent />
    </Suspense>
  );
}
