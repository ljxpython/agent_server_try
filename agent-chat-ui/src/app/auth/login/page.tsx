"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { startOidcLogin } from "@/lib/oidc-client";
import { ensureApiUrlSeeded, setOidcTokenSet } from "@/lib/oidc-storage";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [accountLoading, setAccountLoading] = useState(false);
  const [accountError, setAccountError] = useState<string | null>(null);

  useEffect(() => {
    if ((process.env.NEXT_PUBLIC_OIDC_ENABLED ?? "false") !== "true") {
      setError("OIDC login is disabled. Enable NEXT_PUBLIC_OIDC_ENABLED=true.");
    }
  }, []);

  return (
    <section className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center gap-4 p-6 text-center">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <p className="text-muted-foreground text-sm">
        You can use browser OIDC login or account/password login.
      </p>
      {error ? <p className="text-sm text-red-600">{error}</p> : null}

      <form
        className="w-full rounded-md border p-4 text-left"
        onSubmit={async (event) => {
          event.preventDefault();
          setAccountError(null);
          setAccountLoading(true);
          const formData = new FormData(event.currentTarget);
          const username = String(formData.get("username") ?? "").trim();
          const password = String(formData.get("password") ?? "");

          try {
            const response = await fetch("/api/keycloak-token", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ username, password }),
            });
            const payload = (await response.json().catch(() => ({}))) as {
              access_token?: string;
              expires_at?: number;
              message?: string;
              body?: string;
            };

            if (!response.ok || !payload.access_token) {
              throw new Error(payload.message || payload.body || "Account login failed");
            }

            setOidcTokenSet({
              access_token: payload.access_token,
              expires_at: payload.expires_at,
            });
            ensureApiUrlSeeded();
            router.replace("/workspace/chat");
          } catch (submitError) {
            setAccountError(submitError instanceof Error ? submitError.message : "Account login failed");
          } finally {
            setAccountLoading(false);
          }
        }}
      >
        <p className="mb-3 text-sm font-medium">Account login (Direct Access Grant)</p>
        <div className="mb-3 flex flex-col gap-1">
          <label htmlFor="username" className="text-xs text-muted-foreground">Username</label>
          <input id="username" name="username" required className="rounded-md border px-3 py-2 text-sm" />
        </div>
        <div className="mb-3 flex flex-col gap-1">
          <label htmlFor="password" className="text-xs text-muted-foreground">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            className="rounded-md border px-3 py-2 text-sm"
          />
        </div>
        {accountError ? <p className="mb-2 text-xs text-red-600">{accountError}</p> : null}
        <button
          type="submit"
          disabled={accountLoading}
          className="bg-foreground text-background rounded-md px-4 py-2 text-sm disabled:opacity-60"
        >
          {accountLoading ? "Signing in..." : "Sign in with account"}
        </button>
      </form>

      <p className="text-muted-foreground text-xs">or</p>

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
