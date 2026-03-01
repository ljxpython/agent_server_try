"use client";

import { useCallback, useEffect, useState } from "react";

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

  return (
    <section className="p-6">
      <h2 className="text-xl font-semibold">Projects</h2>
      <p className="text-muted-foreground mt-2 text-sm">Tenant-scoped project list and write operations.</p>

      {!tenantId ? <p className="text-muted-foreground mt-4 text-sm">Select a tenant first.</p> : null}

      {tenantId ? (
        <form className="mt-4 grid gap-2 rounded-md border p-3" onSubmit={onSubmit}>
          <h3 className="text-sm font-medium">{editingId ? "Update project" : "Create project"}</h3>
          <div className="grid gap-2 md:grid-cols-2">
            <input
              className="bg-background rounded-md border px-2 py-1 text-sm"
              placeholder="Project name"
              value={form.name}
              onChange={(event) => setForm({ name: event.target.value })}
              disabled={actionDisabled}
              required
              minLength={2}
              maxLength={128}
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

      {!loading && !error && tenantId ? (
        <div className="mt-4 overflow-auto rounded-md border">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Tenant ID</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((project) => (
                <tr key={project.id} className="border-t">
                  <td className="px-3 py-2">{project.name}</td>
                  <td className="px-3 py-2">{project.tenant_id}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => startEdit(project)}
                        disabled={loading || submitting || removingId === project.id}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => setProjectId(project.id)}
                        disabled={loading || submitting || removingId === project.id || projectId === project.id}
                      >
                        {projectId === project.id ? "Selected" : "Use"}
                      </button>
                      <button
                        type="button"
                        className="rounded-md border px-2 py-1 text-xs disabled:opacity-50"
                        onClick={() => void onDeleteProject(project)}
                        disabled={loading || submitting || removingId === project.id}
                      >
                        {removingId === project.id ? "Deleting..." : "Delete"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {items.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-3 py-4" colSpan={3}>
                    No projects found.
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
