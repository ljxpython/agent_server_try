"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageStateEmpty, PageStateError, PageStateLoading, PageStateNotice } from "@/components/platform/page-state";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { createTenant, deleteTenant, listTenants } from "@/lib/platform-api/tenants";
import type { Tenant } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

type TenantForm = {
  name: string;
  slug: string;
};

const DEFAULT_FORM: TenantForm = {
  name: "",
  slug: "",
};

export default function TenantsPage() {
  const { tenantId, setTenantId, loading: scopeLoading } = useWorkspaceContext();
  const searchParams = useSearchParams();
  const [items, setItems] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [form, setForm] = useState<TenantForm>(DEFAULT_FORM);
  const [selectedTenantIds, setSelectedTenantIds] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const pageSize = 10;

  const query = useMemo(() => searchParams.toString(), [searchParams]);

  const refreshList = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await listTenants();
      setItems(rows);
    } catch (err) {
      setError(toUserErrorMessage(err));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshList();
  }, [refreshList]);

  useEffect(() => {
    setSelectedTenantIds((prev) => prev.filter((id) => items.some((tenant) => tenant.id === id)));
  }, [items]);

  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) {
      return items;
    }
    return items.filter((tenant) => {
      const target = `${tenant.name} ${tenant.slug}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [items, search]);

  const totalPages = Math.max(1, Math.ceil(filteredItems.length / pageSize));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pagedItems = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredItems.slice(start, start + pageSize);
  }, [filteredItems, page]);

  const tenantNameById = useMemo(() => {
    return new Map(items.map((tenant) => [tenant.id, tenant.name]));
  }, [items]);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setNotice(null);

    try {
      const created = await createTenant({
        name: form.name,
        slug: form.slug || undefined,
      });
      setNotice(`Created tenant: ${created.name}`);
      setForm(DEFAULT_FORM);
      setTenantId(created.id);
      await refreshList();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  function toggleTenantSelection(tenantIdToToggle: string) {
    setSelectedTenantIds((prev) => {
      if (prev.includes(tenantIdToToggle)) {
        return prev.filter((id) => id !== tenantIdToToggle);
      }
      return [...prev, tenantIdToToggle];
    });
  }

  function toggleSelectAll(checked: boolean) {
    if (!checked) {
      setSelectedTenantIds((prev) => prev.filter((id) => !pagedItems.some((tenant) => tenant.id === id)));
      return;
    }
    setSelectedTenantIds((prev) => Array.from(new Set([...prev, ...pagedItems.map((tenant) => tenant.id)])));
  }

  async function onBulkDelete() {
    if (selectedTenantIds.length === 0) {
      return;
    }

    if (typeof window !== "undefined") {
      const confirmed = window.confirm(
        `Delete ${selectedTenantIds.length} selected tenant(s)? This will cascade delete projects and assistants in those tenants.`,
      );
      if (!confirmed) {
        return;
      }
    }

    setDeleting(true);
    setError(null);
    setNotice(null);

    let deletedCount = 0;
    const failed: string[] = [];
    const deletingIds = [...selectedTenantIds];

    for (const selectedId of deletingIds) {
      try {
        await deleteTenant(selectedId);
        deletedCount += 1;
      } catch (err) {
        const tenantName = tenantNameById.get(selectedId) ?? "Unknown tenant";
        let reason = toUserErrorMessage(err);
        if (reason.includes("权限被拒绝") || reason.includes("403")) {
          reason = `${reason}（通常表示你在该租户不是 owner/admin）`;
        }
        failed.push(`${tenantName} (${selectedId}): ${reason}`);
      }
    }

    if (deletingIds.includes(tenantId)) {
      setTenantId("");
    }

    setSelectedTenantIds([]);
    await refreshList();

    if (failed.length > 0) {
      setError(`Deleted ${deletedCount}/${deletingIds.length}. Failed: ${failed.join(" | ")}`);
    } else {
      setNotice(`Deleted ${deletedCount} tenant(s).`);
    }

    setDeleting(false);
  }

  const actionDisabled = loading || submitting || deleting || scopeLoading;
  const allSelected = pagedItems.length > 0 && pagedItems.every((tenant) => selectedTenantIds.includes(tenant.id));
  const partiallySelected = selectedTenantIds.length > 0 && !allSelected;
  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Tenants</h2>
      <p className="text-muted-foreground mt-2 text-sm">Create and switch tenant scope for the whole workspace.</p>

      <form className="mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm" onSubmit={onSubmit}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold tracking-tight">Create tenant</h3>
          <span className="text-muted-foreground text-xs">Name 2-128 chars, slug optional</span>
        </div>
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] md:items-end">
          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Name
            <input
              className={fieldClassName}
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="Tenant name"
              minLength={2}
              maxLength={128}
              required
              disabled={actionDisabled}
            />
          </label>
          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Slug (optional)
            <input
              className={fieldClassName}
              value={form.slug}
              onChange={(event) => setForm((prev) => ({ ...prev, slug: event.target.value }))}
              placeholder="tenant-a"
              minLength={2}
              maxLength={128}
              disabled={actionDisabled}
            />
          </label>
          <button
            type="submit"
            className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
            disabled={actionDisabled}
          >
            {submitting ? "Creating..." : "Create"}
          </button>
        </div>
      </form>

      {loading ? <PageStateLoading /> : null}
      {error ? <PageStateError message={error} /> : null}
      {notice ? <PageStateNotice message={notice} /> : null}

      {!loading && !error && items.length === 0 ? <PageStateEmpty message="No tenants found. Create your first tenant." /> : null}

      {!loading && !error && items.length > 0 ? (
        <div className="mt-4 overflow-auto rounded-lg border border-border/80 bg-card/70 shadow-sm">
          <div className="border-b border-border/70 bg-muted/30 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={search}
                  onChange={(event) => {
                    setSearch(event.target.value);
                    setPage(1);
                  }}
                  placeholder="Search by name or slug"
                  className="h-8 rounded-md border border-border bg-background px-2 text-xs"
                  disabled={actionDisabled}
                />
                <button
                  type="button"
                  className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                  onClick={() => {
                    void refreshList();
                  }}
                  disabled={actionDisabled}
                >
                  Refresh
                </button>
                <Link
                  href={tenantId ? `/workspace/tenants/${tenantId}/members${query ? `?${query}` : ""}` : "/workspace/tenants"}
                  className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                >
                  Memberships
                </Link>
              </div>

              <label className="inline-flex items-center gap-2 text-xs text-muted-foreground">
                <input
                  type="checkbox"
                  checked={allSelected}
                  ref={(node) => {
                    if (node) {
                      node.indeterminate = partiallySelected;
                    }
                  }}
                  onChange={(event) => toggleSelectAll(event.target.checked)}
                  disabled={actionDisabled}
                />
                Select current page
              </label>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Selected: {selectedTenantIds.length}</span>
                <button
                  type="button"
                  className={`${buttonBaseClassName} h-8 border-destructive/40 bg-destructive/5 px-2 text-xs text-destructive hover:bg-destructive/10`}
                  disabled={actionDisabled || selectedTenantIds.length === 0}
                  onClick={() => {
                    void onBulkDelete();
                  }}
                >
                  {deleting ? "Deleting..." : "Delete selected"}
                </button>
              </div>
            </div>
          </div>
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Select</th>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Slug</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {pagedItems.map((tenant) => {
                const active = tenantId === tenant.id;
                const membersHref = query
                  ? `/workspace/tenants/${tenant.id}/members?${query}`
                  : `/workspace/tenants/${tenant.id}/members`;

                return (
                  <tr key={tenant.id} className="border-t transition-colors hover:bg-muted/30">
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedTenantIds.includes(tenant.id)}
                        onChange={() => toggleTenantSelection(tenant.id)}
                        disabled={actionDisabled}
                        aria-label={`select-tenant-${tenant.id}`}
                      />
                    </td>
                    <td className="px-3 py-2 font-medium">{tenant.name}</td>
                    <td className="px-3 py-2 text-muted-foreground">{tenant.slug}</td>
                    <td className="px-3 py-2 text-muted-foreground">{tenant.status || "active"}</td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                          onClick={() => setTenantId(tenant.id)}
                          disabled={active || actionDisabled}
                        >
                          {active ? "Selected" : "Use"}
                        </button>
                        <Link
                          href={membersHref}
                          className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                        >
                          Manage members
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="flex items-center justify-between border-t border-border/70 px-3 py-2 text-xs text-muted-foreground">
            <span>
              {filteredItems.length === 0 ? "No results" : `Page ${page}/${totalPages} · ${filteredItems.length} result(s)`}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                disabled={actionDisabled || page <= 1}
                onClick={() => setPage((prev) => Math.max(1, prev - 1))}
              >
                Prev
              </button>
              <button
                type="button"
                className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                disabled={actionDisabled || page >= totalPages}
                onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
              >
                Next
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
