"use client";

import { listProjects } from "@/lib/platform-api/projects";
import { listTenants } from "@/lib/platform-api/tenants";
import type { Project, Tenant } from "@/lib/platform-api/types";
import { logClient } from "@/lib/client-logger";
import { useQueryState } from "nuqs";
import type { ReactNode } from "react";
import { createContext, useContext, useEffect, useMemo, useState } from "react";

type WorkspaceContextValue = {
  tenantId: string;
  setTenantId: (value: string) => void;
  projectId: string;
  setProjectId: (value: string) => void;
  assistantId: string;
  setAssistantId: (value: string) => void;
  tenants: Tenant[];
  projects: Project[];
  loading: boolean;
};

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

function isStaleTenantScopeError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return message.includes("tenant_access_denied") || message.includes("Tenant membership not found");
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [tenantId, setTenantId] = useQueryState("tenantId", {
    defaultValue: process.env.NEXT_PUBLIC_TENANT_ID ?? "",
  });
  const [projectId, setProjectId] = useQueryState("projectId", {
    defaultValue: process.env.NEXT_PUBLIC_PROJECT_ID ?? "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: "",
  });
  const [, setThreadId] = useQueryState("threadId", {
    defaultValue: "",
  });
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function loadTenants() {
      setLoading(true);
      try {
        const rows = await listTenants();
        if (cancelled) return;
        setTenants(rows);

        const tenantStillValid = rows.some((item) => item.id === tenantId);
        if ((!tenantId || !tenantStillValid) && rows.length > 0) {
          setTenantId(rows[0].id);
        }
      } catch {
        if (!cancelled) {
          setTenants([]);
        }
        logClient({
          level: "error",
          event: "workspace_load_tenants_error",
          message: "Failed to load tenants",
        });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadTenants();

    return () => {
      cancelled = true;
    };
  }, [setTenantId, tenantId]);

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      if (!tenantId || tenants.length === 0) {
        setProjects([]);
        setProjectId("");
        return;
      }

      const tenantStillValid = tenants.some((item) => item.id === tenantId);
      if (!tenantStillValid) {
        setTenantId(tenants[0].id);
        setProjects([]);
        setProjectId("");
        return;
      }

      setLoading(true);
      try {
        const rows = await listProjects(tenantId);
        if (cancelled) return;
        setProjects(rows);

        const projectStillValid = rows.some((item) => item.id === projectId);
        if ((!projectId || !projectStillValid) && rows.length > 0) {
          setProjectId(rows[0].id);
        }
        if (rows.length === 0) {
          setProjectId("");
        }
      } catch (err) {
        if (!cancelled && isStaleTenantScopeError(err)) {
          if (tenants.length > 0 && tenantId !== tenants[0].id) {
            setTenantId(tenants[0].id);
          } else {
            setTenantId("");
          }
          setProjectId("");
          setProjects([]);
          return;
        }

        if (!cancelled) {
          setProjects([]);
        }
        logClient({
          level: "error",
          event: "workspace_load_projects_error",
          message: "Failed to load projects",
          context: {
            tenantId,
          },
        });
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadProjects();

    return () => {
      cancelled = true;
    };
  }, [projectId, setProjectId, setTenantId, tenantId, tenants]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      tenantId: tenantId ?? "",
      setTenantId: (value: string) => {
        setTenantId(value);
        setProjectId("");
        setThreadId(null);
        setAssistantId("");
      },
      projectId: projectId ?? "",
      setProjectId: (value: string) => {
        setProjectId(value);
        setThreadId(null);
        setAssistantId("");
      },
      assistantId: assistantId ?? "",
      setAssistantId,
      tenants,
      projects,
      loading,
    }),
    [assistantId, loading, projectId, projects, setAssistantId, setProjectId, setTenantId, setThreadId, tenantId, tenants],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspaceContext() {
  const context = useContext(WorkspaceContext);
  if (!context) {
    throw new Error("useWorkspaceContext must be used within WorkspaceProvider");
  }
  return context;
}
