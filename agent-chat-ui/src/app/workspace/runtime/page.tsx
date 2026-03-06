"use client";

import { useEffect, useState } from "react";

import {
  listRuntimeModels,
  listRuntimeTools,
  type RuntimeModelItem,
  type RuntimeToolItem,
} from "@/lib/management-api/runtime";


export default function RuntimeCapabilitiesPage() {
  const [models, setModels] = useState<RuntimeModelItem[]>([]);
  const [tools, setTools] = useState<RuntimeToolItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [modelsResponse, toolsResponse] = await Promise.all([
          listRuntimeModels().catch(() => null),
          listRuntimeTools().catch(() => null),
        ]);
        if (cancelled) {
          return;
        }
        setModels(modelsResponse && Array.isArray(modelsResponse.models) ? modelsResponse.models : []);
        setTools(toolsResponse && Array.isArray(toolsResponse.tools) ? toolsResponse.tools : []);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load runtime capabilities");
          setModels([]);
          setTools([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Runtime Models &amp; Tools</h2>
      <p className="text-muted-foreground mt-2 text-sm">
        Read-only view of LangGraph runtime capabilities, including model groups and available tools.
      </p>
      {error ? <p className="mt-3 text-sm text-amber-700">{error}</p> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border/80 bg-card/70 p-4">
          <h3 className="text-sm font-semibold">Models</h3>
          {loading && models.length === 0 ? (
            <p className="mt-2 text-sm">Loading models...</p>
          ) : null}
          {!loading && models.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No models reported by runtime.</p>
          ) : null}
          {models.length > 0 ? (
            <div className="mt-3 overflow-auto rounded-md border border-border/70 bg-background/60">
              <table className="min-w-full text-xs">
                <thead className="bg-muted/70 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">#</th>
                    <th className="px-3 py-2">Model ID</th>
                    <th className="px-3 py-2">Display Name</th>
                    <th className="px-3 py-2">Default</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((model, index) => (
                    <tr key={model.model_id} className="border-t border-border/60">
                      <td className="px-3 py-2 text-muted-foreground">{index + 1}</td>
                      <td className="px-3 py-2 font-mono text-[11px]">{model.model_id}</td>
                      <td className="px-3 py-2">{model.display_name}</td>
                      <td className="px-3 py-2 text-xs">{model.is_default ? "Yes" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>

        <div className="rounded-lg border border-border/80 bg-card/70 p-4">
          <h3 className="text-sm font-semibold">Tools</h3>
          {loading && tools.length === 0 ? (
            <p className="mt-2 text-sm">Loading tools...</p>
          ) : null}
          {!loading && tools.length === 0 ? (
            <p className="mt-2 text-sm text-muted-foreground">No tools reported by runtime.</p>
          ) : null}
          {tools.length > 0 ? (
            <div className="mt-3 overflow-auto rounded-md border border-border/70 bg-background/60">
              <table className="min-w-full text-xs">
                <thead className="bg-muted/70 text-left text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                  <tr>
                    <th className="px-3 py-2">#</th>
                    <th className="px-3 py-2">Name</th>
                    <th className="px-3 py-2">Source</th>
                    <th className="px-3 py-2">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {tools.map((tool, index) => (
                    <tr key={tool.name} className="border-t border-border/60">
                      <td className="px-3 py-2 text-muted-foreground">{index + 1}</td>
                      <td className="px-3 py-2 font-mono text-[11px]">{tool.name}</td>
                      <td className="px-3 py-2 text-[11px] text-muted-foreground">{tool.source}</td>
                      <td className="px-3 py-2">{tool.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
