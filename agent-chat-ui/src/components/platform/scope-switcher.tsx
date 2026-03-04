"use client";

import Link from "next/link";

import { useWorkspaceContext } from "@/providers/WorkspaceContext";

export function ScopeSwitcher() {
  const {
    tenantId,
    setTenantId,
    projectId,
    setProjectId,
    tenants,
    projects,
    loading,
  } = useWorkspaceContext();

  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Tenant</span>
        <select
          value={tenantId}
          onChange={(event) => setTenantId(event.target.value)}
          className="bg-background min-w-[180px] rounded-md border px-2 py-1"
          disabled={loading}
        >
          <option value="">Select tenant</option>
          {tenants.map((tenant) => (
            <option key={tenant.id} value={tenant.id}>
              {tenant.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex items-center gap-2 text-sm">
        <span className="text-muted-foreground">Project</span>
        <select
          value={projectId}
          onChange={(event) => setProjectId(event.target.value)}
          className="bg-background min-w-[180px] rounded-md border px-2 py-1"
          disabled={loading || !tenantId}
        >
          <option value="">Select project</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
      </label>

      {!loading && tenants.length === 0 ? (
        <Link
          href="/workspace/tenants"
          className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted/50"
        >
          Create tenant
        </Link>
      ) : null}

      {!loading && Boolean(tenantId) ? (
        <Link
          href={`/workspace/tenants/${tenantId}/members`}
          className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted/50"
        >
          Memberships
        </Link>
      ) : null}
    </div>
  );
}
