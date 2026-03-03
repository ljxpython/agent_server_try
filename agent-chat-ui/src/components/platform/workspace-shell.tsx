"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

import { AuthControls } from "./auth-controls";
import { ScopeSwitcher } from "./scope-switcher";

const NAV_ITEMS = [
  { href: "/workspace/chat", label: "Chat" },
  { href: "/workspace/projects", label: "Projects" },
  { href: "/workspace/agents", label: "Assistants" },
  { href: "/workspace/runtime-bindings", label: "Environments" },
  { href: "/workspace/audit", label: "Audit" },
  { href: "/workspace/stats", label: "Stats" },
];

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const query = searchParams.toString();

  return (
    <div className="bg-background text-foreground flex min-h-dvh flex-col">
      <header className="bg-background/95 sticky top-0 z-20 border-b border-border/80 px-4 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:px-6">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <h1 className="text-base font-semibold tracking-tight sm:text-lg">Agent Platform</h1>
              <p className="text-muted-foreground text-xs sm:text-sm">Workspace scope: tenant -&gt; project</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 sm:gap-3">
              <ScopeSwitcher />
              <AuthControls />
            </div>
          </div>

          <nav data-testid="workspace-nav" aria-label="Workspace sections" className="flex flex-wrap items-center gap-2">
            {NAV_ITEMS.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={query ? `${item.href}?${query}` : item.href}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "inline-flex items-center rounded-md border px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
                    active
                      ? "border-sidebar-primary/60 bg-sidebar-primary text-sidebar-primary-foreground shadow-sm"
                      : "border-border bg-card text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                  ].join(" ")}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto flex min-h-0 w-full max-w-[1400px] flex-1 flex-col">{children}</main>
    </div>
  );
}
