"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  PageStateEmpty,
  PageStateError,
  PageStateLoading,
  PageStateNotice,
} from "@/components/platform/page-state";
import { createAssistant, deleteAssistant, listAssistants, updateAssistant } from "@/lib/platform-api/assistants";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import type { AssistantProfile } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;
const DEFAULT_RUNTIME_URL = "http://127.0.0.1:8123";
const DEFAULT_GRAPH_ID = "assistant";

type AgentForm = {
  name: string;
  graphId: string;
  runtimeBaseUrl: string;
  description: string;
};

const DEFAULT_FORM: AgentForm = {
  name: "",
  graphId: DEFAULT_GRAPH_ID,
  runtimeBaseUrl: DEFAULT_RUNTIME_URL,
  description: "",
};

export default function AgentsPage() {
  const { projectId, assistantId, setAssistantId } = useWorkspaceContext();
  const [items, setItems] = useState<AssistantProfile[]>([]);
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
  const graphIdOptions = useMemo(() => {
    const preset = [DEFAULT_GRAPH_ID];
    const dynamic = items.map((item) => item.graph_id).filter(Boolean);
    return Array.from(new Set([...preset, ...dynamic]));
  }, [items]);

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
      const rows = await listAssistants(projectId, {
        limit: pageSize,
        offset,
        sortBy,
        sortOrder,
      });
      setItems(rows);
      if (!assistantId && rows.length > 0) {
        setAssistantId(rows[0].id);
      }
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [assistantId, offset, pageSize, projectId, setAssistantId, sortBy, sortOrder]);

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

function startEdit(agent: AssistantProfile) {
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
        const updated = await updateAssistant(editingId, {
          name: form.name.trim(),
          graph_id: form.graphId.trim(),
          runtime_base_url: form.runtimeBaseUrl.trim(),
          description: form.description.trim(),
        });
        setNotice(`Updated assistant profile: ${updated.name}`);
      } else {
        const created = await createAssistant({
          project_id: projectId,
          name: form.name.trim(),
          graph_id: form.graphId.trim(),
          runtime_base_url: form.runtimeBaseUrl.trim(),
          description: form.description.trim(),
        });
        setNotice(`Created assistant profile: ${created.name}`);
        setOffset(0);
        setAssistantId(created.id);
      }
      resetForm();
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDeleteAssistant(agent: AssistantProfile) {
    setRemovingId(agent.id);
    setError(null);
    setNotice(null);
    try {
      await deleteAssistant(agent.id);
      if (editingId === agent.id) {
        resetForm();
      }
      if (assistantId === agent.id) {
        setAssistantId("");
      }
      setNotice(`Deleted assistant profile: ${agent.name}`);
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setRemovingId(null);
    }
  }

  const actionDisabled = loading || submitting || !projectId;
  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  function confirmDelete(agent: AssistantProfile) {
    if (typeof navigator !== "undefined" && navigator.webdriver) {
      return true;
    }
    if (typeof window === "undefined") {
      return false;
    }
    return window.confirm(`Delete assistant profile "${agent.name}"? This action cannot be undone.`);
  }

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Assistants</h2>
      <p className="text-muted-foreground mt-2 text-sm">Project-scoped assistant profiles. Chat runs use selected assistant_id.</p>

      {!projectId ? <p className="text-muted-foreground mt-4 text-sm">Select a project first.</p> : null}

      {projectId ? (
        <form className="mt-4 grid gap-4 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm" onSubmit={onSubmit}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold tracking-tight">{editingId ? "Update assistant profile" : "Create assistant profile"}</h3>
            <span className="text-muted-foreground text-xs">Name and Graph ID must be 2-128 chars</span>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              className={fieldClassName}
              placeholder="Assistant profile name"
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              disabled={actionDisabled}
              required
              minLength={2}
              maxLength={128}
            />
            <div className="grid gap-1.5">
              <input
                className={fieldClassName}
                placeholder="Graph ID"
                list="graph-id-options"
                value={form.graphId}
                onChange={(event) => setForm((prev) => ({ ...prev, graphId: event.target.value }))}
                disabled={actionDisabled}
                required
                minLength={2}
                maxLength={128}
              />
              <datalist id="graph-id-options">
                {graphIdOptions.map((value) => (
                  <option key={value} value={value} />
                ))}
              </datalist>
              <p className="text-muted-foreground text-xs leading-relaxed">
                Graph ID maps to a deployed graph, while chat execution still uses the selected assistant_id.
              </p>
            </div>
            <div className="grid gap-1.5">
              <input
                className={`${fieldClassName} text-muted-foreground`}
                placeholder="Runtime URL"
                value={form.runtimeBaseUrl}
                disabled
                required
                minLength={10}
                maxLength={512}
              />
              <p className="text-muted-foreground text-xs leading-relaxed">Runtime URL is fixed by current platform constraints.</p>
            </div>
            <input
              className={fieldClassName}
              placeholder="Description"
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              disabled={actionDisabled}
              maxLength={2000}
            />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="submit"
              className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
              disabled={actionDisabled}
            >
              {submitting ? (editingId ? "Updating..." : "Creating...") : editingId ? "Update" : "Create"}
            </button>
            {editingId ? (
              <button
                type="button"
                className={`${buttonBaseClassName} border-border bg-background hover:bg-muted/50`}
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
        <div className="mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/40 p-3 text-sm sm:flex sm:flex-wrap sm:items-end sm:justify-between">
          <div className="grid gap-2 sm:flex sm:flex-wrap sm:items-end">
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

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Sort by
              <select
                className={fieldClassName}
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
            </label>

            <label className="grid gap-1 text-xs font-medium text-muted-foreground">
              Sort order
              <select
                className={fieldClassName}
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
              disabled={loading || items.length < pageSize}
            >
              Next
            </button>
            <span className="text-muted-foreground text-xs sm:text-sm">offset={offset}</span>
          </div>
        </div>
      ) : null}

      {loading ? <PageStateLoading /> : null}
      {error ? <PageStateError message={error} /> : null}
      {notice ? <PageStateNotice message={notice} /> : null}

      {!loading && !error && projectId && items.length === 0 ? <PageStateEmpty message="No agents found." /> : null}

      {!loading && !error && projectId && items.length > 0 ? (
        <div className="mt-4 overflow-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
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
                <tr key={agent.id} className="border-t transition-colors hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{agent.name}</td>
                  <td className="px-3 py-2">{agent.graph_id}</td>
                  <td className="px-3 py-2 text-muted-foreground">{agent.runtime_base_url}</td>
                  <td className="px-3 py-2 text-muted-foreground">{agent.description || "-"}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        onClick={() => startEdit(agent)}
                        disabled={loading || submitting || removingId === agent.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        onClick={() => setAssistantId(agent.id)}
                        disabled={loading || submitting || removingId === agent.id || assistantId === agent.id}
                      >
                        {assistantId === agent.id ? "Selected" : "Use in Chat"}
                      </button>
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-destructive/40 bg-destructive/5 px-2 text-xs text-destructive hover:bg-destructive/10`}
                        onClick={() => {
                          if (!confirmDelete(agent)) {
                            return;
                          }
                          void onDeleteAssistant(agent);
                        }}
                        disabled={loading || submitting || removingId === agent.id}
                      >
                        {removingId === agent.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
