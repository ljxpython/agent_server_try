"use client";

import { useEffect, useState } from "react";

import { startOidcLogin } from "@/lib/oidc-client";

export default function LoginPage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if ((process.env.NEXT_PUBLIC_OIDC_ENABLED ?? "false") !== "true") {
      setError("OIDC login is disabled. Enable NEXT_PUBLIC_OIDC_ENABLED=true.");
    }
  }, []);

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="text-muted-foreground text-sm">
        Use Keycloak browser login (OIDC Authorization Code + PKCE).
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}
      <button
        type="button"
        className="bg-foreground text-background rounded-md px-4 py-2 text-sm"
        onClick={() => startOidcLogin("/workspace/chat")}
        disabled={Boolean(error)}
      >
        Continue with Keycloak
      </button>
    </section>
  );
}
