"use client";

import { useEffect, useState } from "react";

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

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!tenantId) {
        setItems([]);
        setTotal(0);
        setOffset(0);
        setError(null);
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
      const blob = await exportTenantAuditLogsCSV(tenantId, filters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `audit-${tenantId}-${Date.now()}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(toUserErrorMessage(err));
    }
  }

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Audit</h2>
      <p className="text-muted-foreground mt-2 text-sm">Latest tenant audit logs.</p>

      {!tenantId ? <p className="text-muted-foreground mt-4 text-sm">Select a tenant first.</p> : null}

      {tenantId ? (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <select
            className="bg-background rounded-md border px-2 py-1"
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

          <input
            className="bg-background rounded-md border px-2 py-1"
            placeholder="path prefix"
            value={filters.pathPrefix ?? ""}
            onChange={(event) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, pathPrefix: event.target.value }));
            }}
          />

          <select
            className="bg-background rounded-md border px-2 py-1"
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

          <select
            className="bg-background rounded-md border px-2 py-1"
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

          <input
            className="bg-background w-28 rounded-md border px-2 py-1"
            placeholder="status"
            value={filters.statusCode ?? ""}
            onChange={(event) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, statusCode: event.target.value }));
            }}
          />

          <input
            type="datetime-local"
            className="bg-background rounded-md border px-2 py-1"
            value={filters.fromTime ?? ""}
            onChange={(event) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, fromTime: event.target.value }));
            }}
          />

          <input
            type="datetime-local"
            className="bg-background rounded-md border px-2 py-1"
            value={filters.toTime ?? ""}
            onChange={(event) => {
              setOffset(0);
              setFilters((prev) => ({ ...prev, toTime: event.target.value }));
            }}
          />

          <button
            type="button"
            className="bg-background rounded-md border px-2 py-1 disabled:opacity-50"
            onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
            disabled={loading || offset === 0}
          >
            Prev
          </button>
          <button
            type="button"
            className="bg-background rounded-md border px-2 py-1 disabled:opacity-50"
            onClick={() => setOffset((prev) => prev + pageSize)}
            disabled={loading || offset + pageSize >= total}
          >
            Next
          </button>
          <button
            type="button"
            className="bg-background rounded-md border px-2 py-1 disabled:opacity-50"
            onClick={onExport}
            disabled={loading}
          >
            Export CSV
          </button>
          <span className="text-muted-foreground text-xs">
            total={total}, offset={offset}
          </span>
        </div>
      ) : null}

      {loading ? <p className="mt-4 text-sm">Loading...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      {!loading && !error && tenantId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="bg-muted/50 text-left">
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
                <tr key={row.id} className="border-t">
                  <td className="px-3 py-2">{new Date(row.created_at).toLocaleString()}</td>
                  <td className="px-3 py-2">{row.method}</td>
                  <td className="px-3 py-2">{row.path}</td>
                  <td className="px-3 py-2">{row.status_code}</td>
                  <td className="px-3 py-2">{row.plane}</td>
                  <td className="px-3 py-2">{row.duration_ms}</td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={6}>
                    No audit logs found.
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
