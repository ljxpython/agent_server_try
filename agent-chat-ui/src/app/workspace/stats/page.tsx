"use client";

import { useEffect, useState } from "react";

import {
  PageStateEmpty,
  PageStateError,
  PageStateLoading,
  PageStateNotice,
} from "@/components/platform/page-state";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { queryTenantAuditStats } from "@/lib/platform-api/stats";
import type { AuditStats } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const GROUP_OPTIONS = ["path", "status_code", "user_id", "plane"] as const;

export default function StatsPage() {
  const { tenantId } = useWorkspaceContext();
  const [groupBy, setGroupBy] = useState<(typeof GROUP_OPTIONS)[number]>("path");
  const [stats, setStats] = useState<AuditStats>({ by: "path", items: [] });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!tenantId) {
        setStats({ by: groupBy, items: [] });
        setError(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const data = await queryTenantAuditStats(tenantId, groupBy);
        if (cancelled) return;
        setStats(data);
      } catch (err) {
        if (cancelled) return;
        setError(toUserErrorMessage(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    run();

    return () => {
      cancelled = true;
    };
  }, [tenantId, groupBy]);

  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Stats</h2>
      <p className="text-muted-foreground mt-2 text-sm">Tenant audit aggregation stats.</p>

      {!tenantId ? <PageStateNotice message="Select a tenant first." /> : null}

      {tenantId ? (
        <div className="mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/40 p-3 text-sm sm:flex sm:flex-wrap sm:items-end sm:justify-between">
          <label className="grid gap-1 text-xs font-medium text-muted-foreground sm:min-w-[220px]">
            Group by
            <select
              className={fieldClassName}
              value={groupBy}
              onChange={(event) =>
                setGroupBy(event.target.value as (typeof GROUP_OPTIONS)[number])
              }
              disabled={loading}
            >
              {GROUP_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <p className="text-muted-foreground text-xs sm:text-sm">
            grouped by <span className="font-medium text-foreground">{stats.by}</span>
          </p>
        </div>
      ) : null}

      {loading ? <PageStateLoading /> : null}
      {error ? <PageStateError message={error} /> : null}

      {!loading && !error && tenantId && stats.items.length === 0 ? <PageStateEmpty message="No stats found." /> : null}

      {!loading && !error && tenantId && stats.items.length > 0 ? (
        <div className="mt-4 overflow-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <table className="w-full min-w-[560px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Key</th>
                <th className="px-3 py-2 text-right">Count</th>
              </tr>
            </thead>
            <tbody>
              {stats.items.map((item) => (
                <tr key={item.key} className="border-t transition-colors hover:bg-muted/30">
                  <td className="px-3 py-2 align-top">
                    <span className="block whitespace-normal break-all font-mono text-xs sm:text-sm">
                      {item.key || "(empty)"}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right align-top font-medium tabular-nums">{item.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
