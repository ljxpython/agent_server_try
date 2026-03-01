"use client";

import { useEffect, useState } from "react";

import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { listAgents } from "@/lib/platform-api/agents";
import type { Agent } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

export default function AgentsPage() {
  const { projectId } = useWorkspaceContext();
  const [items, setItems] = useState<Agent[]>([]);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(PAGE_SIZE);
  const [sortBy, setSortBy] = useState<"created_at" | "name">("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!projectId) {
        setItems([]);
        setOffset(0);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const rows = await listAgents(projectId, {
          limit: pageSize,
          offset,
          sortBy,
          sortOrder,
        });
        if (cancelled) return;
        setItems(rows);
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
  }, [projectId, offset, pageSize, sortBy, sortOrder]);

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Agents</h2>
      <p className="text-muted-foreground mt-2 text-sm">Project-scoped agent list from platform API.</p>

      {!projectId ? (
        <p className="text-muted-foreground mt-4 text-sm">Select a project first.</p>
      ) : null}

      {projectId ? (
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

          <select
            className="bg-background rounded-md border px-2 py-1"
            value={sortBy}
            onChange={(event) => {
              setOffset(0);
              setSortBy(event.target.value as "created_at" | "name");
            }}
            disabled={loading}
          >
            <option value="created_at">sort created_at</option>
            <option value="name">sort name</option>
          </select>

          <select
            className="bg-background rounded-md border px-2 py-1"
            value={sortOrder}
            onChange={(event) => {
              setOffset(0);
              setSortOrder(event.target.value as "asc" | "desc");
            }}
            disabled={loading}
          >
            <option value="desc">desc</option>
            <option value="asc">asc</option>
          </select>

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
            disabled={loading || items.length < pageSize}
          >
            Next
          </button>
          <span className="text-muted-foreground">offset={offset}</span>
        </div>
      ) : null}

      {loading ? <p className="mt-4 text-sm">Loading...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      {!loading && !error && projectId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Graph ID</th>
                <th className="px-3 py-2">Runtime URL</th>
                <th className="px-3 py-2">Description</th>
              </tr>
            </thead>
            <tbody>
              {items.map((agent) => (
                <tr key={agent.id} className="border-t">
                  <td className="px-3 py-2">{agent.name}</td>
                  <td className="px-3 py-2">{agent.graph_id}</td>
                  <td className="px-3 py-2">{agent.runtime_base_url}</td>
                  <td className="px-3 py-2">{agent.description || "-"}</td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={4}>
                    No agents found.
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
