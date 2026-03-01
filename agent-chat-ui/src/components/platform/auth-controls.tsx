"use client";

import { useEffect, useState } from "react";

import { buildLogoutUrl, startOidcLogin } from "@/lib/oidc-client";
import { clearOidcTokenSet, getOidcTokenSet } from "@/lib/oidc-storage";

export function AuthControls() {
  const [loggedIn, setLoggedIn] = useState(false);
  const oidcEnabled = (process.env.NEXT_PUBLIC_OIDC_ENABLED ?? "false") === "true";

  useEffect(() => {
    const tokenSet = getOidcTokenSet();
    setLoggedIn(Boolean(tokenSet?.access_token));
  }, []);

  if (!oidcEnabled) {
    return null;
  }

  return loggedIn ? (
    <button
      type="button"
      className="bg-background rounded-md border px-3 py-1 text-sm"
      onClick={() => {
        clearOidcTokenSet();
        const url = buildLogoutUrl(`${window.location.origin}/auth/login`);
        window.location.href = url;
      }}
    >
      Sign out
    </button>
  ) : (
    <button
      type="button"
      className="bg-foreground text-background rounded-md px-3 py-1 text-sm"
      onClick={() => startOidcLogin(window.location.pathname + window.location.search)}
    >
      Sign in
    </button>
  );
}
