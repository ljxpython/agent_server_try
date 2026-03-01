"use client";

import { useEffect, useState } from "react";

import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { listAgents } from "@/lib/platform-api/agents";
import { listRuntimeBindings } from "@/lib/platform-api/runtime-bindings";
import type { Agent, RuntimeBinding } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

export default function RuntimeBindingsPage() {
  const { projectId } = useWorkspaceContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agentId, setAgentId] = useState("");
  const [bindings, setBindings] = useState<RuntimeBinding[]>([]);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(PAGE_SIZE);
  const [sortBy, setSortBy] = useState<"created_at" | "environment">("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!projectId) {
        setAgents([]);
        setAgentId("");
        setBindings([]);
        setOffset(0);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const agentRows = await listAgents(projectId);
        if (cancelled) return;
        setAgents(agentRows);
        const selected = agentRows[0]?.id ?? "";
        setAgentId(selected);
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
  }, [projectId]);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      if (!agentId) {
        setBindings([]);
        setOffset(0);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const rows = await listRuntimeBindings(agentId, {
          limit: pageSize,
          offset,
          sortBy,
          sortOrder,
        });
        if (cancelled) return;
        setBindings(rows);
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
  }, [agentId, offset, pageSize, sortBy, sortOrder]);

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Runtime Bindings</h2>
      <p className="text-muted-foreground mt-2 text-sm">Select an agent to view environment bindings.</p>

      {!projectId ? <p className="text-muted-foreground mt-4 text-sm">Select a project first.</p> : null}

      {projectId ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <label className="text-sm">
            <span className="text-muted-foreground mr-2">Agent</span>
            <select
              className="bg-background rounded-md border px-2 py-1"
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
              disabled={loading || agents.length === 0}
            >
              <option value="">Select agent</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </label>

          <select
            className="bg-background rounded-md border px-2 py-1 text-sm"
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
            className="bg-background rounded-md border px-2 py-1 text-sm"
            value={sortBy}
            onChange={(event) => {
              setOffset(0);
              setSortBy(event.target.value as "created_at" | "environment");
            }}
            disabled={loading}
          >
            <option value="created_at">sort created_at</option>
            <option value="environment">sort environment</option>
          </select>

          <select
            className="bg-background rounded-md border px-2 py-1 text-sm"
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
            className="bg-background rounded-md border px-2 py-1 text-sm disabled:opacity-50"
            onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
            disabled={loading || offset === 0 || !agentId}
          >
            Prev
          </button>
          <button
            type="button"
            className="bg-background rounded-md border px-2 py-1 text-sm disabled:opacity-50"
            onClick={() => setOffset((prev) => prev + pageSize)}
            disabled={loading || bindings.length < pageSize || !agentId}
          >
            Next
          </button>
          <span className="text-muted-foreground text-xs">offset={offset}</span>
        </div>
      ) : null}

      {loading ? <p className="mt-4 text-sm">Loading...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}

      {!loading && !error && agentId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Environment</th>
                <th className="px-3 py-2">Assistant ID</th>
                <th className="px-3 py-2">Graph ID</th>
                <th className="px-3 py-2">Runtime URL</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((binding) => (
                <tr key={binding.id} className="border-t">
                  <td className="px-3 py-2">{binding.environment}</td>
                  <td className="px-3 py-2">{binding.langgraph_assistant_id}</td>
                  <td className="px-3 py-2">{binding.langgraph_graph_id}</td>
                  <td className="px-3 py-2">{binding.runtime_base_url}</td>
                </tr>
              ))}
              {bindings.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={4}>
                    No runtime bindings found.
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
