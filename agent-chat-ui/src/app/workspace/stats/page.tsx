"use client";

import { useEffect, useState } from "react";

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

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Stats</h2>
      <p className="text-muted-foreground mt-2 text-sm">Tenant audit aggregation stats.</p>

      {!tenantId ? <p className="text-muted-foreground mt-4 text-sm">Select a tenant first.</p> : null}

      {tenantId ? (
        <div className="mt-4">
          <label className="text-sm">
            <span className="text-muted-foreground mr-2">Group by</span>
            <select
              className="bg-background rounded-md border px-2 py-1"
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
        </div>
      ) : null}

      {loading ? <p className="mt-4 text-sm">Loading...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      {!loading && !error && tenantId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Key</th>
                <th className="px-3 py-2">Count</th>
              </tr>
            </thead>
            <tbody>
              {stats.items.map((item) => (
                <tr key={item.key} className="border-t">
                  <td className="px-3 py-2">{item.key || "(empty)"}</td>
                  <td className="px-3 py-2">{item.count}</td>
                </tr>
              ))}
              {stats.items.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={2}>
                    No stats found.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
