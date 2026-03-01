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
  agentId: string;
  setAgentId: (value: string) => void;
  tenants: Tenant[];
  projects: Project[];
  loading: boolean;
};

const WorkspaceContext = createContext<WorkspaceContextValue | undefined>(undefined);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [tenantId, setTenantId] = useQueryState("tenantId", {
    defaultValue: process.env.NEXT_PUBLIC_TENANT_ID ?? "",
  });
  const [projectId, setProjectId] = useQueryState("projectId", {
    defaultValue: process.env.NEXT_PUBLIC_PROJECT_ID ?? "",
  });
  const [agentId, setAgentId] = useQueryState("agentId", {
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

        if (!tenantId && rows.length > 0) {
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
      if (!tenantId) {
        setProjects([]);
        setProjectId("");
        return;
      }

      setLoading(true);
      try {
        const rows = await listProjects(tenantId);
        if (cancelled) return;
        setProjects(rows);

        if (!projectId && rows.length > 0) {
          setProjectId(rows[0].id);
        }
      } catch {
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
  }, [projectId, setProjectId, tenantId]);

  const value = useMemo<WorkspaceContextValue>(
    () => ({
      tenantId: tenantId ?? "",
      setTenantId: (value: string) => {
        setTenantId(value);
        setProjectId("");
        setAgentId("");
      },
      projectId: projectId ?? "",
      setProjectId: (value: string) => {
        setProjectId(value);
        setAgentId("");
      },
      agentId: agentId ?? "",
      setAgentId,
      tenants,
      projects,
      loading,
    }),
    [agentId, loading, projectId, projects, setAgentId, setProjectId, setTenantId, tenantId, tenants],
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
