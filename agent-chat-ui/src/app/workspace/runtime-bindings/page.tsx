"use client";

import { useCallback, useEffect, useState } from "react";

import {
  PageStateEmpty,
  PageStateError,
  PageStateLoading,
  PageStateNotice,
} from "@/components/platform/page-state";
import { listAssistants } from "@/lib/platform-api/assistants";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import {
  deleteEnvironmentMapping,
  listEnvironmentMappings,
  upsertEnvironmentMapping,
} from "@/lib/platform-api/environment-mappings";
import type { AssistantProfile, EnvironmentMapping } from "@/lib/platform-api/types";
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
  const { projectId, assistantId, setAssistantId } = useWorkspaceContext();
  const [assistants, setAssistants] = useState<AssistantProfile[]>([]);
  const [bindings, setBindings] = useState<EnvironmentMapping[]>([]);
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
    if (!assistantId) {
      setBindings([]);
      setOffset(0);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await listEnvironmentMappings(assistantId, {
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
  }, [assistantId, offset, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    let cancelled = false;

    async function loadAssistants() {
      if (!projectId) {
        setAssistants([]);
        setAssistantId("");
        setBindings([]);
        setOffset(0);
        setError(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const assistantRows = await listAssistants(projectId);
        if (cancelled) return;
        setAssistants(assistantRows);
        if (assistantRows.length === 0) {
          setAssistantId("");
        } else if (!assistantId || !assistantRows.some((a) => a.id === assistantId)) {
          setAssistantId(assistantRows[0].id);
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

    void loadAssistants();
    return () => {
      cancelled = true;
    };
  }, [assistantId, projectId, setAssistantId]);

  useEffect(() => {
    void refreshBindings();
  }, [refreshBindings]);

  async function onUpsertBinding(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!assistantId) return;

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const saved = await upsertEnvironmentMapping(assistantId, {
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

  async function onDeleteBinding(binding: EnvironmentMapping) {
    if (!assistantId) return;
    setRemovingId(binding.id);
    setError(null);
    setNotice(null);
    try {
      await deleteEnvironmentMapping(assistantId, binding.id);
      setNotice(`Deleted environment mapping: ${binding.environment}`);
      await refreshBindings();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setRemovingId(null);
    }
  }

  function startEditBinding(binding: EnvironmentMapping) {
    setBindingForm({
      environment: binding.environment as BindingForm["environment"],
      assistantId: binding.langgraph_assistant_id,
      graphId: binding.langgraph_graph_id,
      runtimeBaseUrl: binding.runtime_base_url,
    });
    setNotice(`Editing environment mapping: ${binding.environment}`);
  }

  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const panelClassName = "mt-4 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm";
  const filterPanelClassName = "mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/40 p-4 text-sm shadow-sm";

  function confirmDelete(binding: EnvironmentMapping) {
    if (typeof navigator !== "undefined" && navigator.webdriver) {
      return true;
    }
    if (typeof window === "undefined") {
      return false;
    }
    return window.confirm(`Delete environment mapping "${binding.environment}"? This action cannot be undone.`);
  }

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Environments</h2>
      <p className="text-muted-foreground mt-2 text-sm">Environment endpoint mapping for the selected assistant profile.</p>

      {!projectId ? <PageStateNotice message="Select a project first." /> : null}

      {projectId ? (
        <div className={filterPanelClassName}>
          <div className="grid gap-3">
            <label className="grid gap-1 text-xs font-medium text-muted-foreground sm:max-w-sm">
              Assistant profile
              <select
                className={fieldClassName}
                value={assistantId}
                onChange={(event) => setAssistantId(event.target.value)}
                disabled={loading || assistants.length === 0}
              >
                <option value="">Select assistant profile</option>
                {assistants.map((assistant) => (
                  <option key={assistant.id} value={assistant.id}>
                    {assistant.name}
                  </option>
                ))}
              </select>
            </label>

            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
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
                    setSortBy(event.target.value as "created_at" | "environment");
                  }}
                  disabled={loading}
                >
                  <option value="created_at">sort created_at</option>
                  <option value="environment">sort environment</option>
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
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-3 sm:border-0 sm:pt-0">
            <button
              type="button"
              className={`${buttonBaseClassName} border-border bg-background hover:bg-muted/50`}
              onClick={() => setOffset((prev) => Math.max(0, prev - pageSize))}
              disabled={loading || offset === 0 || !assistantId}
            >
              Prev
            </button>
            <button
              type="button"
              className={`${buttonBaseClassName} border-border bg-background hover:bg-muted/50`}
              onClick={() => setOffset((prev) => prev + pageSize)}
              disabled={loading || bindings.length < pageSize || !assistantId}
            >
              Next
            </button>
            <span className="text-muted-foreground text-xs sm:text-sm">offset={offset}</span>
          </div>
        </div>
      ) : null}

      {projectId && assistantId ? (
        <form className={`${panelClassName} grid gap-4`} onSubmit={onUpsertBinding}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold tracking-tight">Create / Update environment mapping</h3>
            <span className="text-muted-foreground text-xs">Assistant and Graph IDs must be 2-128 chars</span>
          </div>
          <div className="grid gap-3">
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                Environment
                <select
                  className={fieldClassName}
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
              </label>

              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                Runtime URL
                <input
                  className={`${fieldClassName} text-muted-foreground`}
                  placeholder="Runtime URL"
                  value={bindingForm.runtimeBaseUrl}
                  disabled
                  required
                  minLength={10}
                  maxLength={512}
                />
              </label>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                Assistant ID
                <input
                  className={fieldClassName}
                  placeholder="Assistant ID"
                  value={bindingForm.assistantId}
                  onChange={(event) => setBindingForm((prev) => ({ ...prev, assistantId: event.target.value }))}
                  disabled={loading || submitting}
                  required
                  minLength={2}
                  maxLength={128}
                />
              </label>

              <label className="grid gap-1 text-xs font-medium text-muted-foreground">
                Graph ID
                <input
                  className={fieldClassName}
                  placeholder="Graph ID"
                  value={bindingForm.graphId}
                  onChange={(event) => setBindingForm((prev) => ({ ...prev, graphId: event.target.value }))}
                  disabled={loading || submitting}
                  required
                  minLength={2}
                  maxLength={128}
                />
              </label>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="submit"
              className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
              disabled={loading || submitting}
            >
              {submitting ? "Saving..." : "Save mapping"}
            </button>
          </div>
        </form>
      ) : null}

      {loading ? <PageStateLoading /> : null}
      {error ? <PageStateError message={error} /> : null}
      {notice ? <PageStateNotice message={notice} /> : null}

      {!loading && !error && projectId && assistants.length === 0 ? (
        <PageStateEmpty message="No assistant profiles found for this project." />
      ) : null}

      {!loading && !error && projectId && assistants.length > 0 && !assistantId ? (
        <PageStateNotice message="Select an assistant profile to view environment mappings." />
      ) : null}

      {!loading && !error && assistantId && bindings.length === 0 ? <PageStateEmpty message="No environment mappings found." /> : null}

      {!loading && !error && assistantId && bindings.length > 0 ? (
        <div className="mt-4 overflow-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
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
                <tr key={binding.id} className="border-t transition-colors hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{binding.environment}</td>
                  <td className="px-3 py-2">{binding.langgraph_assistant_id}</td>
                  <td className="px-3 py-2">{binding.langgraph_graph_id}</td>
                  <td className="text-muted-foreground px-3 py-2">{binding.runtime_base_url}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        onClick={() => startEditBinding(binding)}
                        disabled={loading || submitting || removingId === binding.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-destructive/40 bg-destructive/5 px-2 text-xs text-destructive hover:bg-destructive/10`}
                        onClick={() => {
                          if (!confirmDelete(binding)) {
                            return;
                          }
                          void onDeleteBinding(binding);
                        }}
                        disabled={loading || submitting || removingId === binding.id}
                      >
                        {removingId === binding.id ? "Deleting..." : "Delete"}
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
