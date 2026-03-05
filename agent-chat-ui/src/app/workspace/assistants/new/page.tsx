"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { createAssistant, getAssistantParameterSchema } from "@/lib/management-api/assistants";
import { listGraphsPage } from "@/lib/management-api/graphs";
import { useWorkspaceContext } from "@/providers/WorkspaceContext";

type SchemaProperty = {
  type?: string;
  required?: boolean;
};

type SchemaSection = {
  key?: string;
  title?: string;
  type?: string;
  properties?: Record<string, SchemaProperty>;
};

type ParameterSchemaResponse = {
  graph_id?: string;
  schema_version?: string;
  sections?: SchemaSection[];
};

function parseObjectJson(raw: string, fieldName: string): Record<string, unknown> {
  const normalized = raw.trim();
  if (!normalized) {
    return {};
  }
  const parsed = JSON.parse(normalized);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${fieldName} must be a JSON object`);
  }
  return parsed as Record<string, unknown>;
}

export default function CreateAssistantPage() {
  const router = useRouter();
  const { projectId } = useWorkspaceContext();
  const [graphId, setGraphId] = useState("assistant");
  const [graphOptions, setGraphOptions] = useState<string[]>([]);
  const [graphLoading, setGraphLoading] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [assistantId, setAssistantId] = useState("");
  const [config, setConfig] = useState("{}");
  const [context, setContext] = useState("{}");
  const [metadata, setMetadata] = useState("{}");
  const [enableLocalTools, setEnableLocalTools] = useState<"" | "true" | "false">("");
  const [enableLocalMcp, setEnableLocalMcp] = useState<"" | "true" | "false">("");
  const [schema, setSchema] = useState<ParameterSchemaResponse | null>(null);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [configFields, setConfigFields] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const configPropertyDefs = useMemo(() => {
    const sections = Array.isArray(schema?.sections) ? schema?.sections : [];
    const configSection = sections.find((section) => section?.key === "config");
    const properties = configSection?.properties;
    if (!properties || typeof properties !== "object") {
      return [] as Array<{ key: string; type: string; required: boolean }>;
    }
    return Object.entries(properties).map(([key, value]) => ({
      key,
      type: typeof value?.type === "string" ? value.type : "string",
      required: Boolean(value?.required),
    }));
  }, [schema]);

  const requestBodyPreview = useMemo(() => {
    const normalizedGraphId = graphId.trim();
    const normalizedName = name.trim();
    const payload: Record<string, unknown> = {};
    if (normalizedGraphId) {
      payload.graph_id = normalizedGraphId;
    }
    if (normalizedName) {
      payload.name = normalizedName;
    }
    if (description.trim()) {
      payload.description = description.trim();
    }
    if (assistantId.trim()) {
      payload.assistant_id = assistantId.trim();
    }

    const configObject = parseObjectJson(config, "config");
    if (enableLocalTools === "true") {
      configObject.enable_local_tools = true;
    } else if (enableLocalTools === "false") {
      configObject.enable_local_tools = false;
    } else {
      delete configObject.enable_local_tools;
    }
    if (enableLocalMcp === "true") {
      configObject.enable_local_mcp = true;
    } else if (enableLocalMcp === "false") {
      configObject.enable_local_mcp = false;
    } else {
      delete configObject.enable_local_mcp;
    }
    if (Object.keys(configObject).length > 0) {
      payload.config = configObject;
    }

    const contextObject = parseObjectJson(context, "context");
    if (Object.keys(contextObject).length > 0) {
      payload.context = contextObject;
    }

    const metadataObject = parseObjectJson(metadata, "metadata");
    if (Object.keys(metadataObject).length > 0) {
      payload.metadata = metadataObject;
    }

    return payload;
  }, [assistantId, config, context, description, enableLocalMcp, enableLocalTools, graphId, metadata, name]);

  useEffect(() => {
    if (!projectId) {
      setGraphOptions([]);
      return;
    }
    setGraphLoading(true);
    void listGraphsPage(projectId, {
      limit: 30,
      offset: 0,
      query: graphId.trim() || undefined,
    })
      .then((payload) => {
        const next = payload.items
          .map((item) => item.graph_id)
          .filter((value): value is string => typeof value === "string" && value.trim().length > 0);
        setGraphOptions(next);
      })
      .catch(() => setGraphOptions([]))
      .finally(() => setGraphLoading(false));
  }, [graphId, projectId]);

  useEffect(() => {
    const normalizedGraphId = graphId.trim();
    if (!normalizedGraphId) {
      setSchema(null);
      setSchemaError(null);
      return;
    }

    setSchemaLoading(true);
    setSchemaError(null);
    void getAssistantParameterSchema(normalizedGraphId, projectId || undefined)
      .then((payload) => {
        const normalized = payload as ParameterSchemaResponse;
        setSchema(normalized);
      })
      .catch((err) => {
        setSchema(null);
        setSchemaError(err instanceof Error ? err.message : "Failed to load parameter schema");
      })
      .finally(() => setSchemaLoading(false));
  }, [graphId, projectId]);

  useEffect(() => {
    const baseConfig = parseObjectJson(config, "config");
    const nextFields: Record<string, string> = {};
    for (const field of configPropertyDefs) {
      const rawValue = baseConfig[field.key];
      nextFields[field.key] =
        rawValue === null || rawValue === undefined
          ? ""
          : typeof rawValue === "string"
            ? rawValue
            : String(rawValue);
    }
    setConfigFields(nextFields);
  }, [config, configPropertyDefs]);

  function applyConfigFieldValue(key: string, value: string, valueType: string) {
    setConfigFields((prev) => ({ ...prev, [key]: value }));
    const currentConfig = parseObjectJson(config, "config");
    if (!value.trim()) {
      delete currentConfig[key];
      setConfig(JSON.stringify(currentConfig, null, 2));
      return;
    }

    if (valueType === "number") {
      const parsed = Number(value);
      if (!Number.isFinite(parsed)) {
        return;
      }
      currentConfig[key] = parsed;
      setConfig(JSON.stringify(currentConfig, null, 2));
      return;
    }

    if (valueType === "boolean") {
      currentConfig[key] = value === "true";
      setConfig(JSON.stringify(currentConfig, null, 2));
      return;
    }

    currentConfig[key] = value;
    setConfig(JSON.stringify(currentConfig, null, 2));
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      setError("Please select a project first.");
      return;
    }
    const normalizedName = name.trim();
    const normalizedGraphId = graphId.trim();
    if (!normalizedName || !normalizedGraphId) {
      setError("Name and graph id are required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      const configObject = parseObjectJson(config, "config");
      const contextObject = parseObjectJson(context, "context");
      const metadataObject = parseObjectJson(metadata, "metadata");
      if (enableLocalTools === "true") {
        configObject.enable_local_tools = true;
      } else if (enableLocalTools === "false") {
        configObject.enable_local_tools = false;
      } else {
        delete configObject.enable_local_tools;
      }
      if (enableLocalMcp === "true") {
        configObject.enable_local_mcp = true;
      } else if (enableLocalMcp === "false") {
        configObject.enable_local_mcp = false;
      } else {
        delete configObject.enable_local_mcp;
      }

      const payload: {
        graph_id: string;
        name: string;
        description?: string;
        assistant_id?: string;
        config?: Record<string, unknown>;
        context?: Record<string, unknown>;
        metadata?: Record<string, unknown>;
      } = {
        graph_id: normalizedGraphId,
        name: normalizedName,
      };
      if (description.trim()) {
        payload.description = description.trim();
      }
      if (assistantId.trim()) {
        payload.assistant_id = assistantId.trim();
      }
      if (Object.keys(configObject).length > 0) {
        payload.config = configObject;
      }
      if (Object.keys(contextObject).length > 0) {
        payload.context = contextObject;
      }
      if (Object.keys(metadataObject).length > 0) {
        payload.metadata = metadataObject;
      }

      const created = await createAssistant(projectId, {
        ...payload,
      });
      setNotice(`Created assistant: ${created.name}`);
      router.replace("/workspace/assistants");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create assistant");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="p-4 sm:p-6">
      <h2 className="text-xl font-semibold tracking-tight">Create Assistant</h2>
      <p className="text-muted-foreground mt-2 text-sm">Create a project-scoped assistant with dynamic parameters.</p>

      <form className="mt-4 grid gap-3 rounded-lg border border-border/80 bg-card/70 p-4" onSubmit={onSubmit}>
        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Graph ID
          <input
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            list="assistant-graph-options"
            value={graphId}
            onChange={(event) => setGraphId(event.target.value)}
            placeholder={graphLoading ? "Searching graphs..." : "Type to fuzzy search, or pick from dropdown"}
            disabled={submitting}
            required
          />
          <datalist id="assistant-graph-options">
            {graphOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </datalist>
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Name
          <input
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={submitting}
            required
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Description
          <textarea
            className="min-h-20 rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Optional Assistant ID
          <input
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={assistantId}
            onChange={(event) => setAssistantId(event.target.value)}
            disabled={submitting}
            placeholder="If empty, upstream generates one"
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          enable_local_tools
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={enableLocalTools}
            onChange={(event) => setEnableLocalTools(event.target.value === "true" ? "true" : event.target.value === "false" ? "false" : "")}
            disabled={submitting}
          >
            <option value="">Not set (omit)</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          enable_local_mcp
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={enableLocalMcp}
            onChange={(event) => setEnableLocalMcp(event.target.value === "true" ? "true" : event.target.value === "false" ? "false" : "")}
            disabled={submitting}
          >
            <option value="">Not set (omit)</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>

        <div className="grid gap-2 rounded-md border border-border/80 bg-background/50 p-3">
          <p className="text-xs font-medium text-muted-foreground">Parameter Schema</p>
          {schemaLoading ? <p className="text-xs">Loading schema...</p> : null}
          {schemaError ? <p className="text-xs text-red-600">{schemaError}</p> : null}
          {!schemaLoading && !schemaError ? (
            <p className="text-xs text-muted-foreground">
              graph={schema?.graph_id || graphId.trim() || "-"} · version={schema?.schema_version || "v1"}
            </p>
          ) : null}
        </div>

        {configPropertyDefs.length > 0 ? (
          <div className="grid gap-2 rounded-md border border-border/80 bg-background/50 p-3">
            <p className="text-xs font-medium text-muted-foreground">Config Fields (schema-driven)</p>
            {configPropertyDefs.map((field) => (
              <label key={field.key} className="grid gap-1 text-xs font-medium text-muted-foreground">
                {field.key}
                <input
                  className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                  value={configFields[field.key] ?? ""}
                  onChange={(event) => applyConfigFieldValue(field.key, event.target.value, field.type)}
                  placeholder={field.type}
                  disabled={submitting}
                  required={field.required}
                />
              </label>
            ))}
          </div>
        ) : null}

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Config (JSON object)
          <textarea
            className="min-h-28 rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
            value={config}
            onChange={(event) => setConfig(event.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Context (JSON object)
          <textarea
            className="min-h-28 rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
            value={context}
            onChange={(event) => setContext(event.target.value)}
            disabled={submitting}
          />
        </label>

        <label className="grid gap-1 text-xs font-medium text-muted-foreground">
          Metadata (JSON object)
          <textarea
            className="min-h-28 rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
            value={metadata}
            onChange={(event) => setMetadata(event.target.value)}
            disabled={submitting}
          />
        </label>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="submit"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-foreground px-3 text-sm font-medium text-background disabled:opacity-50"
            disabled={submitting}
          >
            {submitting ? "Creating..." : "Create Assistant"}
          </button>
          <Link
            href="/workspace/assistants"
            className="inline-flex h-9 items-center justify-center rounded-md border border-border bg-background px-3 text-sm"
          >
            Back to Assistants
          </Link>
        </div>
      </form>

      {error ? <p className="mt-4 text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="mt-4 text-sm text-emerald-700">{notice}</p> : null}

      <div className="mt-4 rounded-lg border border-border/80 bg-card/70 p-4">
        <p className="text-xs font-medium text-muted-foreground">Create assistant request body</p>
        <pre className="mt-2 overflow-auto rounded border border-border bg-background p-3 text-xs">
          {JSON.stringify(requestBodyPreview, null, 2)}
        </pre>
      </div>
    </section>
  );
}
