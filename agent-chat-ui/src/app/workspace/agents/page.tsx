"use client";

import { useCallback, useEffect, useState } from "react";

import { createAgent, deleteAgent, listAgents, updateAgent } from "@/lib/platform-api/agents";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import type { Agent } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

type AgentForm = {
  name: string;
  graphId: string;
  runtimeBaseUrl: string;
  description: string;
};

const DEFAULT_FORM: AgentForm = {
  name: "",
  graphId: "",
  runtimeBaseUrl: "",
  description: "",
};

export default function AgentsPage() {
  const { projectId } = useWorkspaceContext();
  const [items, setItems] = useState<Agent[]>([]);
  const [offset, setOffset] = useState(0);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZE_OPTIONS)[number]>(PAGE_SIZE);
  const [sortBy, setSortBy] = useState<"created_at" | "name">("created_at");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("desc");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<AgentForm>(DEFAULT_FORM);

  const refreshList = useCallback(async () => {
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
      setItems(rows);
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [offset, pageSize, projectId, sortBy, sortOrder]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!projectId) {
      setForm(DEFAULT_FORM);
      setEditingId(null);
      setNotice(null);
      setError(null);
    }
  }, [projectId]);

  function startEdit(agent: Agent) {
    setEditingId(agent.id);
    setForm({
      name: agent.name,
      graphId: agent.graph_id,
      runtimeBaseUrl: agent.runtime_base_url,
      description: agent.description,
    });
    setNotice(null);
    setError(null);
  }

  function resetForm() {
    setEditingId(null);
    setForm(DEFAULT_FORM);
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) return;

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      if (editingId) {
        const updated = await updateAgent(editingId, {
          name: form.name.trim(),
          graph_id: form.graphId.trim(),
          runtime_base_url: form.runtimeBaseUrl.trim(),
          description: form.description.trim(),
        });
        setNotice(`Updated agent: ${updated.name}`);
      } else {
        const created = await createAgent({
          project_id: projectId,
          name: form.name.trim(),
          graph_id: form.graphId.trim(),
          runtime_base_url: form.runtimeBaseUrl.trim(),
          description: form.description.trim(),
        });
        setNotice(`Created agent: ${created.name}`);
        setOffset(0);
      }
      resetForm();
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDeleteAgent(agent: Agent) {
    setRemovingId(agent.id);
    setError(null);
    setNotice(null);
    try {
      await deleteAgent(agent.id);
      if (editingId === agent.id) {
        resetForm();
      }
      setNotice(`Deleted agent: ${agent.name}`);
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setRemovingId(null);
    }
  }

  const actionDisabled = loading || submitting || !projectId;

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Agents</h2>
      <p className="text-muted-foreground mt-2 text-sm">Project-scoped agent list and write operations.</p>

      {!projectId ? <p className="text-muted-foreground mt-4 text-sm">Select a project first.</p> : null}

      {projectId ? (
        <form className="mt-4 grid gap-2 rounded-md border p-3" onSubmit={onSubmit}>
          <h3 className="text-sm font-medium">{editingId ? "Update agent" : "Create agent"}</h3>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Agent name"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              disabled={actionDisabled}
              required
              minLength={2}
              maxLength={128}
            />
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Graph ID"
              value={form.graphId}
              onChange={(event) => setForm((prev) => ({ ...prev, graphId: event.target.value }))}
              disabled={actionDisabled}
              required
              minLength={2}
              maxLength={128}
            />
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Runtime URL"
              value={form.runtimeBaseUrl}
              onChange={(event) => setForm((prev) => ({ ...prev, runtimeBaseUrl: event.target.value }))}
              disabled={actionDisabled}
              required
              minLength={10}
              maxLength={512}
            />
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Description"
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              disabled={actionDisabled}
              maxLength={2000}
            />
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              className="bg-background rounded-md border px-3 py-1 text-sm disabled:opacity-50"
              disabled={actionDisabled}
            >
              {submitting ? (editingId ? "Updating..." : "Creating...") : editingId ? "Update" : "Create"}
            </button>
            {editingId ? (
              <button
                type="button"
                className="bg-background rounded-md border px-3 py-1 text-sm disabled:opacity-50"
                onClick={resetForm}
                disabled={actionDisabled}
              >
                Cancel edit
              </button>
            ) : null}
          </div>
        </form>
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
      {notice ? <p className="mt-4 text-sm text-green-700">{notice}</p> : null}

      {!loading && !error && projectId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Graph ID</th>
                <th className="px-3 py-2">Runtime URL</th>
                <th className="px-3 py-2">Description</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((agent) => (
                <tr key={agent.id} className="border-t">
                  <td className="px-3 py-2">{agent.name}</td>
                  <td className="px-3 py-2">{agent.graph_id}</td>
                  <td className="px-3 py-2">{agent.runtime_base_url}</td>
                  <td className="px-3 py-2">{agent.description || "-"}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => startEdit(agent)}
                        disabled={loading || submitting || removingId === agent.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => void onDeleteAgent(agent)}
                        disabled={loading || submitting || removingId === agent.id}
                      >
                        {removingId === agent.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={5}>
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
