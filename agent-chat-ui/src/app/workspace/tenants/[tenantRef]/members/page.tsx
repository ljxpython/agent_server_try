"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageStateError, PageStateNotice } from "@/components/platform/page-state";
import { toUserErrorMessage } from "@/lib/platform-api/errors";
import { addMembership, listMemberships, removeMembership } from "@/lib/platform-api/memberships";
import type { MembershipListItem, MembershipRole } from "@/lib/platform-api/types";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

type AddForm = {
  externalSubject: string;
  userId: string;
  email: string;
  role: MembershipRole;
};

const DEFAULT_ADD_FORM: AddForm = {
  externalSubject: "",
  userId: "",
  email: "",
  role: "member",
};

export default function TenantMembersPage() {
  const params = useParams<{ tenantRef: string }>();
  const searchParams = useSearchParams();
  const { tenantId, setTenantId, tenants } = useWorkspaceContext();
  const tenantRef = typeof params.tenantRef === "string" ? params.tenantRef : "";
  const query = useMemo(() => searchParams.toString(), [searchParams]);

  const [addForm, setAddForm] = useState<AddForm>(DEFAULT_ADD_FORM);
  const [removeRef, setRemoveRef] = useState("");
  const [submittingAdd, setSubmittingAdd] = useState(false);
  const [submittingRemove, setSubmittingRemove] = useState(false);
  const [loadingList, setLoadingList] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [memberships, setMemberships] = useState<MembershipListItem[]>([]);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const pageSize = 10;

  const selectedTenant = tenants.find((item) => item.id === tenantRef);
  const backHref = query ? `/workspace/tenants?${query}` : "/workspace/tenants";

  const refreshMemberships = useCallback(async () => {
    if (!tenantRef) {
      setMemberships([]);
      return;
    }

    setLoadingList(true);
    try {
      const rows = await listMemberships(tenantRef, { limit: 500, offset: 0 });
      setMemberships(rows);
    } catch (err) {
      setError(toUserErrorMessage(err));
      setMemberships([]);
    } finally {
      setLoadingList(false);
    }
  }, [tenantRef]);

  useEffect(() => {
    void refreshMemberships();
  }, [refreshMemberships]);

  const filteredMemberships = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) {
      return memberships;
    }
    return memberships.filter((item) => {
      const target = `${item.email} ${item.external_subject} ${item.user_id} ${item.role}`.toLowerCase();
      return target.includes(keyword);
    });
  }, [memberships, search]);

  const totalPages = Math.max(1, Math.ceil(filteredMemberships.length / pageSize));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pagedMemberships = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredMemberships.slice(start, start + pageSize);
  }, [filteredMemberships, page]);

  async function onAddMembership(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmittingAdd(true);
    setError(null);
    setNotice(null);

    try {
      const row = await addMembership(tenantRef, {
        external_subject: addForm.externalSubject || undefined,
        user_id: addForm.userId || undefined,
        email: addForm.email || undefined,
        role: addForm.role,
      });

      setNotice(`Membership upserted: user=${row.user_id}, role=${row.role}`);
      setAddForm(DEFAULT_ADD_FORM);
      await refreshMemberships();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmittingAdd(false);
    }
  }

  async function onRemoveMembership(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmittingRemove(true);
    setError(null);
    setNotice(null);

    try {
      const row = await removeMembership(tenantRef, removeRef.trim());
      setNotice(`Membership delete result: user=${row.user_id}, deleted=${String(row.deleted)}`);
      setRemoveRef("");
      await refreshMemberships();
    } catch (err) {
      setError(toUserErrorMessage(err));
    } finally {
      setSubmittingRemove(false);
    }
  }

  const disabled = submittingAdd || submittingRemove || loadingList;
  const fieldClassName =
    "h-9 rounded-md border border-border bg-background px-3 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50";
  const buttonBaseClassName =
    "inline-flex h-9 items-center justify-center rounded-md border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50";

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Tenant members</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        Manage memberships for tenant <span className="font-medium text-foreground">{selectedTenant?.name || tenantRef}</span>.
      </p>

      {tenantId !== tenantRef ? (
        <PageStateNotice
          className="mt-4"
          message={
            <span>
              Current scope tenant is different.
              <button
                type="button"
                className="ml-2 underline underline-offset-2"
                onClick={() => setTenantId(tenantRef)}
              >
                Switch to this tenant
              </button>
            </span>
          }
        />
      ) : null}

      <div className="mt-4 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold tracking-tight">Members</h3>
          <div className="flex flex-wrap items-center gap-2">
            <input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Search by email / subject / user id"
              className="h-8 rounded-md border border-border bg-background px-2 text-xs"
              disabled={disabled}
            />
            <button
              type="button"
              className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
              onClick={() => {
                void refreshMemberships();
              }}
              disabled={disabled}
            >
              Refresh
            </button>
          </div>
        </div>

        {pagedMemberships.length > 0 ? (
          <div className="mt-3 overflow-auto rounded-md border border-border/70">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-muted/70 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-3 py-2">Email</th>
                  <th className="px-3 py-2">Subject</th>
                  <th className="px-3 py-2">User ID</th>
                  <th className="px-3 py-2">Role</th>
                </tr>
              </thead>
              <tbody>
                {pagedMemberships.map((item) => (
                  <tr key={`${item.tenant_id}:${item.user_id}`} className="border-t transition-colors hover:bg-muted/30">
                    <td className="px-3 py-2">{item.email}</td>
                    <td className="px-3 py-2 text-muted-foreground">{item.external_subject}</td>
                    <td className="px-3 py-2 text-muted-foreground">{item.user_id}</td>
                    <td className="px-3 py-2 text-muted-foreground">{item.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between border-t border-border/70 px-3 py-2 text-xs text-muted-foreground">
              <span>
                {filteredMemberships.length === 0
                  ? "No members"
                  : `Page ${page}/${totalPages} · ${filteredMemberships.length} member(s)`}
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                  disabled={disabled || page <= 1}
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                >
                  Prev
                </button>
                <button
                  type="button"
                  className={`${buttonBaseClassName} h-8 border-border bg-background px-2 text-xs hover:bg-muted/50`}
                  disabled={disabled || page >= totalPages}
                  onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground mt-3 text-xs">No membership records found for this tenant.</p>
        )}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <form className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm" onSubmit={onAddMembership}>
          <h3 className="text-sm font-semibold tracking-tight">Add or update membership</h3>
          <p className="text-muted-foreground text-xs">Use user_id or external_subject to identify target user.</p>

          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            External subject (optional)
            <input
              className={fieldClassName}
              value={addForm.externalSubject}
              onChange={(event) => setAddForm((prev) => ({ ...prev, externalSubject: event.target.value }))}
              placeholder="keycloak-subject-or-external-id"
              disabled={disabled}
            />
          </label>

          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            User ID (optional)
            <input
              className={fieldClassName}
              value={addForm.userId}
              onChange={(event) => setAddForm((prev) => ({ ...prev, userId: event.target.value }))}
              placeholder="uuid"
              disabled={disabled}
            />
          </label>

          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Email (optional)
            <input
              className={fieldClassName}
              type="email"
              value={addForm.email}
              onChange={(event) => setAddForm((prev) => ({ ...prev, email: event.target.value }))}
              placeholder="user@example.com"
              disabled={disabled}
            />
          </label>

          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            Role
            <select
              className={fieldClassName}
              value={addForm.role}
              onChange={(event) => setAddForm((prev) => ({ ...prev, role: event.target.value as MembershipRole }))}
              disabled={disabled}
            >
              <option value="owner">owner</option>
              <option value="admin">admin</option>
              <option value="member">member</option>
            </select>
          </label>

          <button
            type="submit"
            className={`${buttonBaseClassName} border-border bg-foreground text-background hover:bg-foreground/90`}
            disabled={disabled}
          >
            {submittingAdd ? "Saving..." : "Save membership"}
          </button>
        </form>

        <form className="grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4 shadow-sm" onSubmit={onRemoveMembership}>
          <h3 className="text-sm font-semibold tracking-tight">Remove membership</h3>
          <p className="text-muted-foreground text-xs">Provide user_ref as UUID or external subject.</p>

          <label className="grid gap-1 text-xs font-medium text-muted-foreground">
            User ref
            <input
              className={fieldClassName}
              value={removeRef}
              onChange={(event) => setRemoveRef(event.target.value)}
              placeholder="user-id or external-subject"
              required
              disabled={disabled}
            />
          </label>

          <button
            type="submit"
            className={`${buttonBaseClassName} border-destructive/40 bg-destructive/5 text-destructive hover:bg-destructive/10`}
            disabled={disabled}
          >
            {submittingRemove ? "Removing..." : "Remove membership"}
          </button>
        </form>
      </div>

      {error ? <PageStateError message={error} /> : null}
      {notice ? <PageStateNotice message={notice} /> : null}

      <div className="mt-4">
        <Link href={backHref} className="text-sm underline underline-offset-2">
          Back to tenants
        </Link>
      </div>
    </section>
  );
}
