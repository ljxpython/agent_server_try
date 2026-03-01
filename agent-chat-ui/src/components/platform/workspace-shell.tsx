"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { AuthControls } from "./auth-controls";
import { ScopeSwitcher } from "./scope-switcher";

const NAV_ITEMS = [
  { href: "/workspace/chat", label: "Chat" },
  { href: "/workspace/agents", label: "Agents" },
  { href: "/workspace/runtime-bindings", label: "Runtime" },
  { href: "/workspace/audit", label: "Audit" },
  { href: "/workspace/stats", label: "Stats" },
];

export function WorkspaceShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="bg-background text-foreground min-h-screen">
      <header className="sticky top-0 z-20 border-b bg-white/95 px-4 py-3 backdrop-blur sm:px-6">
        <div className="mx-auto flex max-w-[1400px] flex-col gap-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h1 className="text-lg font-semibold">Agent Platform</h1>
              <p className="text-muted-foreground text-xs">Workspace scope: tenant -&gt; project</p>
            </div>
            <div className="flex items-center gap-3">
              <ScopeSwitcher />
              <AuthControls />
            </div>
          </div>

          <nav className="flex flex-wrap items-center gap-2">
            {NAV_ITEMS.map((item) => {
              const active = pathname?.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "rounded-md border px-3 py-1 text-sm transition-colors",
                    active ? "bg-foreground text-background" : "hover:bg-muted",
                  ].join(" ")}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-[1400px]">{children}</main>
    </div>
  );
}
