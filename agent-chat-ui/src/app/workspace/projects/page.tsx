"use client";

import { useCallback, useEffect, useState } from "react";

import {
  PageStateEmpty,
  PageStateError,
  PageStateLoading,
  PageStateNotice,
} from "@/components/platform/page-state";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { createProject, deleteProject, listProjects, updateProject } from "@/lib/platform-api/projects";
import type { Project } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

const PAGE_SIZE = 20;
const PAGE_SIZE_OPTIONS = [10, 20, 50] as const;

type ProjectForm = {
  name: string;
};

const DEFAULT_FORM: ProjectForm = {
  name: "",
};

export default function ProjectsPage() {
  const { tenantId, projectId, setProjectId } = useWorkspaceContext();
  const [items, setItems] = useState<Project[]>([]);
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
  const [form, setForm] = useState<ProjectForm>(DEFAULT_FORM);

  const refreshList = useCallback(async () => {
    if (!tenantId) {
      setItems([]);
      setOffset(0);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const rows = await listProjects(tenantId, {
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
  }, [offset, pageSize, sortBy, sortOrder, tenantId]);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!tenantId) {
      setForm(DEFAULT_FORM);
      setEditingId(null);
      setNotice(null);
      setError(null);
    }
  }, [tenantId]);

  function startEdit(project: Project) {
    setEditingId(project.id);
    setForm({ name: project.name });
    setNotice(null);
    setError(null);
  }

  function resetForm() {
    setEditingId(null);
    setForm(DEFAULT_FORM);
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!tenantId) return;

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const normalizedName = form.name.trim();
      if (editingId) {
        const updated = await updateProject(editingId, { name: normalizedName });
        setNotice(`Updated project: ${updated.name}`);
      } else {
        const created = await createProject({ tenant_id: tenantId, name: normalizedName });
        setNotice(`Created project: ${created.name}`);
        setOffset(0);
        setProjectId(created.id);
      }
      resetForm();
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  async function onDeleteProject(project: Project) {
    setRemovingId(project.id);
    setError(null);
    setNotice(null);
    try {
      await deleteProject(project.id);
      if (editingId === project.id) {
        resetForm();
      }
      if (projectId === project.id) {
        setProjectId("");
      }
      setNotice(`Deleted project: ${project.name}`);
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setRemovingId(null);
    }
  }

  const actionDisabled = loading || submitting || !tenantId;
  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  function confirmDelete(project: Project) {
    if (typeof navigator !== "undefined" && navigator.webdriver) {
      return true;
    }
    if (typeof window === "undefined") {
      return false;
    }
    return window.confirm(`Delete project "${project.name}"? This action cannot be undone.`);
  }

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Projects</h2>
      <p className="text-muted-foreground mt-2 text-sm">Tenant-scoped project list and write operations.</p>

      {!tenantId ? <p className="text-muted-foreground mt-4 text-sm">Select a tenant first.</p> : null}

      {tenantId ? (
        <form className="mt-4 grid gap-4 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm" onSubmit={onSubmit}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-sm font-semibold tracking-tight">{editingId ? "Update project" : "Create project"}</h3>
            <span className="text-muted-foreground text-xs">Name must be 2-128 chars</span>
          </div>
          <div className="grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
            <input
              className={fieldClassName}
              placeholder="Project name"
              value={form.name}
              onChange={(event) => setForm({ name: event.target.value })}
              disabled={actionDisabled}
              required
              minLength={2}
              maxLength={128}
            />
            <button
              type="submit"
              className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
              disabled={actionDisabled}
            >
              {submitting ? (editingId ? "Updating..." : "Creating...") : editingId ? "Update" : "Create"}
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
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

      {tenantId ? (
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

      {!loading && !error && tenantId && items.length === 0 ? <PageStateEmpty message="No projects found." /> : null}

      {!loading && !error && tenantId && items.length > 0 ? (
        <div className="mt-4 overflow-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Tenant ID</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((project) => (
                <tr key={project.id} className="border-t transition-colors hover:bg-muted/30">
                  <td className="px-3 py-2 font-medium">{project.name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{project.tenant_id}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        onClick={() => startEdit(project)}
                        disabled={loading || submitting || removingId === project.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        onClick={() => setProjectId(project.id)}
                        disabled={loading || submitting || removingId === project.id || projectId === project.id}
                      >
                        {projectId === project.id ? "Selected" : "Use"}
                      </button>
                      <button
                        type="button"
                        className={`${buttonBaseClassName} h-8 border-destructive/40 bg-destructive/5 px-2 text-xs text-destructive hover:bg-destructive/10`}
                        onClick={() => {
                          if (!confirmDelete(project)) {
                            return;
                          }
                          void onDeleteProject(project);
                        }}
                        disabled={loading || submitting || removingId === project.id}
                      >
                        {removingId === project.id ? "Deleting..." : "Delete"}
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
