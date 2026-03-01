"use client";

import { useCallback, useEffect, useState } from "react";

import { listAgents } from "@/lib/platform-api/agents";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { deleteRuntimeBinding, listRuntimeBindings, upsertRuntimeBinding } from "@/lib/platform-api/runtime-bindings";
import type { Agent, RuntimeBinding } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const ENV_OPTIONS = ["dev", "staging", "prod"] as const;
const DEFAULT_RUNTIME_URL = "http://127.0.0.1:8123";
const DEFAULT_ASSISTANT_ID = "assistant";
const DEFAULT_GRAPH_ID = "assistant";

type BindingForm = {
  environment: (typeof ENV_OPTIONS)[number];
  assistantId: string;
  graphId: string;
  runtimeBaseUrl: string;
};

const DEFAULT_BINDING_FORM: BindingForm = {
  environment: "dev",
  assistantId: DEFAULT_ASSISTANT_ID,
  graphId: DEFAULT_GRAPH_ID,
  runtimeBaseUrl: DEFAULT_RUNTIME_URL,
};

export default function RuntimeBindingsPage() {
  const { projectId, agentId, setAgentId } = useWorkspaceContext();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [bindings, setBindings] = useState<RuntimeBinding[]>([]);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(PAGE_SIZE);
  const [sortBy, setSortBy] = useState<"created_at" | "environment">("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [bindingForm, setBindingForm] = useState<BindingForm>(DEFAULT_BINDING_FORM);

  const refreshBindings = useCallback(async () => {
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
      setBindings(rows);
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [agentId, offset, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    let cancelled = false;

    async function loadAgents() {
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
        if (agentRows.length === 0) {
          setAgentId("");
        } else if (!agentId || !agentRows.some((a) => a.id === agentId)) {
          setAgentId(agentRows[0].id);
        }
      } catch (err) {
        if (cancelled) return;
        setError(toUserErrorMessage(err));
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadAgents();
    return () => {
      cancelled = true;
    };
  }, [agentId, projectId, setAgentId]);

  useEffect(() => {
    void refreshBindings();
  }, [refreshBindings]);

  async function onUpsertBinding(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!agentId) return;

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await upsertRuntimeBinding(agentId, {
        environment: bindingForm.environment,
        langgraph_assistant_id: bindingForm.assistantId.trim(),
        langgraph_graph_id: bindingForm.graphId.trim(),
        runtime_base_url: bindingForm.runtimeBaseUrl.trim(),
      });
      setNotice(`Saved environment mapping: ${saved.environment}`);
      await refreshBindings();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDeleteBinding(binding: RuntimeBinding) {
    if (!agentId) return;
    setRemovingId(binding.id);
    setError(null);
    setNotice(null);
    try {
      await deleteRuntimeBinding(agentId, binding.id);
      setNotice(`Deleted environment mapping: ${binding.environment}`);
      await refreshBindings();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setRemovingId(null);
    }
  }

  function startEditBinding(binding: RuntimeBinding) {
    setBindingForm({
      environment: binding.environment as BindingForm["environment"],
      assistantId: binding.langgraph_assistant_id,
      graphId: binding.langgraph_graph_id,
      runtimeBaseUrl: binding.runtime_base_url,
    });
    setNotice(`Editing environment mapping: ${binding.environment}`);
  }

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Environments</h2>
      <p className="text-muted-foreground mt-2 text-sm">Environment endpoint mapping for the selected assistant profile.</p>

      {!projectId ? <p className="text-muted-foreground mt-4 text-sm">Select a project first.</p> : null}

      {projectId ? (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <label className="text-sm">
            <span className="text-muted-foreground mr-2">Assistant profile</span>
            <select
              className="bg-background rounded-md border px-2 py-1"
              value={agentId}
              onChange={(event) => setAgentId(event.target.value)}
              disabled={loading || agents.length === 0}
            >
              <option value="">Select assistant profile</option>
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

      {projectId && agentId ? (
        <form className="mt-4 grid gap-2 rounded-md border p-3" onSubmit={onUpsertBinding}>
          <h3 className="text-sm font-medium">Create / Update environment mapping</h3>
          <div className="grid gap-2 md:grid-cols-2">
            <select
              className="bg-background rounded-md border px-2 py-1 text-sm"
              value={bindingForm.environment}
              onChange={(event) =>
                setBindingForm((prev) => ({ ...prev, environment: event.target.value as BindingForm["environment"] }))
              }
              disabled={loading || submitting}
            >
              {ENV_OPTIONS.map((env) => (
                <option key={env} value={env}>
                  {env}
                </option>
              ))}
            </select>
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Assistant ID"
              value={bindingForm.assistantId}
              onChange={(event) => setBindingForm((prev) => ({ ...prev, assistantId: event.target.value }))}
              disabled={loading || submitting}
              required
              minLength={2}
              maxLength={128}
            />
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Graph ID"
              value={bindingForm.graphId}
              onChange={(event) => setBindingForm((prev) => ({ ...prev, graphId: event.target.value }))}
              disabled={loading || submitting}
              required
              minLength={2}
              maxLength={128}
            />
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Runtime URL"
              value={bindingForm.runtimeBaseUrl}
              disabled
              required
              minLength={10}
              maxLength={512}
            />
          </div>
          <div>
            <button
              type="submit"
              className="bg-background rounded-md border px-3 py-1 text-sm disabled:opacity-50"
              disabled={loading || submitting}
            >
              {submitting ? "Saving..." : "Save binding"}
            </button>
          </div>
        </form>
      ) : null}

      {loading ? <p className="mt-4 text-sm">Loading...</p> : null}
      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="mt-4 text-sm text-green-700">{notice}</p> : null}

      {!loading && !error && agentId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Environment</th>
                <th className="px-3 py-2">Assistant ID</th>
                <th className="px-3 py-2">Graph ID</th>
                <th className="px-3 py-2">Runtime URL</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bindings.map((binding) => (
                <tr key={binding.id} className="border-t">
                  <td className="px-3 py-2">{binding.environment}</td>
                  <td className="px-3 py-2">{binding.langgraph_assistant_id}</td>
                  <td className="px-3 py-2">{binding.langgraph_graph_id}</td>
                  <td className="px-3 py-2">{binding.runtime_base_url}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => startEditBinding(binding)}
                        disabled={loading || submitting || removingId === binding.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => void onDeleteBinding(binding)}
                        disabled={loading || submitting || removingId === binding.id}
                      >
                        {removingId === binding.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {bindings.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={5}>
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
