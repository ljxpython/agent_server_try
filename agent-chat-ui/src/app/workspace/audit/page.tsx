"use client";

import { useEffect, useState } from "react";

import { PageStateEmpty, PageStateError, PageStateLoading, PageStateNotice } from "@/components/platform/page-state";
import {
  type AuditQueryOptions,
  exportTenantAuditLogsCSV,
  listTenantAuditLogs,
} from "@/lib/platform-api/audit";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import type { AuditLog } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 50;
const PAGE_SIZE_OPTIONS = [20, 50, 100] as const;

export default function AuditPage() {
  const { tenantId } = useWorkspaceContext();
  const [items, setItems] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(PAGE_SIZE);
  const [filters, setFilters] = useState<AuditQueryOptions>({
    plane: "",
    method: "",
    pathPrefix: "",
    statusCode: "",
    fromTime: "",
    toTime: "",
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!tenantId) {
        setItems([]);
        setTotal(0);
        setOffset(0);
        setError(null);
        setNotice(null);
        return;
      }

      setLoading(true);
      setError(null);
      try {
        const data = await listTenantAuditLogs(tenantId, {
          limit: pageSize,
          offset,
          plane: filters.plane,
          method: filters.method,
          pathPrefix: filters.pathPrefix,
          statusCode: filters.statusCode,
          fromTime: filters.fromTime,
          toTime: filters.toTime,
        });
        if (cancelled) return;
        setItems(data.items);
        setTotal(data.total);
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
  }, [tenantId, offset, filters, pageSize]);

  async function onExport() {
    if (!tenantId) return;
    try {
      setError(null);
      setNotice(null);
      const blob = await exportTenantAuditLogsCSV(tenantId, filters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `audit-${tenantId}-${Date.now()}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
      setNotice("CSV export started.");
    } catch (err) {
      setError(toUserErrorMessage(err));
    }
  }

  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Audit</h2>
      <p className="text-muted-foreground mt-2 text-sm">Latest tenant audit logs.</p>

      {!tenantId ? <PageStateNotice message="Select a tenant first." /> : null}

      {tenantId ? (
        <div className="mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/40 p-3 text-sm">
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Page size
              <select
                className={fieldClassName}
                value={pageSize}
                onChange={(event) => {
                  setOffset(0);
                  setPageSize(Number(event.target.value) as (typeof PAGE_SIZE_OPTIONS)[number]);
                }}
                disabled={loading}
              >
                {PAGE_SIZE_OPTIONS.map((size) => (
                  <option key={size} value={size}>
                    page size {size}
                  </option>
                ))}
              </select>
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground sm:col-span-2 lg:col-span-1">
              Path prefix
              <input
                className={fieldClassName}
                placeholder="path prefix"
                value={filters.pathPrefix ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({ ...prev, pathPrefix: event.target.value }));
                }}
              />
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Method
              <select
                className={fieldClassName}
                value={filters.method ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({
                    ...prev,
                    method: event.target.value as AuditQueryOptions["method"],
                  }));
                }}
              >
                <option value="">All methods</option>
                <option value="GET">GET</option>
                <option value="POST">POST</option>
                <option value="PUT">PUT</option>
                <option value="PATCH">PATCH</option>
                <option value="DELETE">DELETE</option>
              </select>
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Plane
              <select
                className={fieldClassName}
                value={filters.plane ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({
                    ...prev,
                    plane: event.target.value as AuditQueryOptions["plane"],
                  }));
                }}
              >
                <option value="">All planes</option>
                <option value="runtime_proxy">runtime_proxy</option>
                <option value="control_plane">control_plane</option>
                <option value="internal">internal</option>
              </select>
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Status
              <input
                className={fieldClassName}
                placeholder="status"
                value={filters.statusCode ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({ ...prev, statusCode: event.target.value }));
                }}
              />
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              From
              <input
                type="datetime-local"
                className={fieldClassName}
                value={filters.fromTime ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({ ...prev, fromTime: event.target.value }));
                }}
              />
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              To
              <input
                type="datetime-local"
                className={fieldClassName}
                value={filters.toTime ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((prev) => ({ ...prev, toTime: event.target.value }));
                }}
              />
            </label>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={`${buttonBaseClassName} border-border bg-background hover:bg-muted/50`}
              onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
              disabled={loading || offset === 0}
            >
              Prev
            </button>
            <button
              type="button"
              className={`${buttonBaseClassName} border-border bg-background hover:bg-muted/50`}
              onClick={() => setOffset((prev) => prev + pageSize)}
              disabled={loading || offset + pageSize >= total}
            >
              Next
            </button>
            <button
              type="button"
              className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
              onClick={onExport}
              disabled={loading}
            >
              Export CSV
            </button>
            <span className="text-muted-foreground text-xs sm:text-sm">total={total}, offset={offset}</span>
          </div>
        </div>
      ) : null}

      {loading ? <PageStateLoading /> : null}
      {error ? <PageStateError message={error} /> : null}
      {notice ? <PageStateNotice message={notice} /> : null}

      {!loading && !error && tenantId && items.length === 0 ? <PageStateEmpty message="No audit logs found." /> : null}

      {!loading && !error && tenantId && items.length > 0 ? (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <table className="w-full min-w-[980px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Method</th>
                <th className="px-3 py-2">Path</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Plane</th>
                <th className="px-3 py-2">Duration(ms)</th>
              </tr>
            </thead>
            <tbody>
              {items.map((row) => (
                <tr key={row.id} className="border-t transition-colors hover:bg-muted/30">
                  <td className="px-3 py-2 text-xs text-muted-foreground sm:text-sm">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2 font-medium">{row.method}</td>
                  <td className="px-3 py-2 font-mono text-xs sm:text-sm">{row.path}</td>
                  <td className="px-3 py-2 font-medium">{row.status_code}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.plane}</td>
                  <td className="px-3 py-2 text-muted-foreground">{row.duration_ms}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
