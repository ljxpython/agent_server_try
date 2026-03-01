import {
  createContext,
  type FC,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useStream } from "@langchain/langgraph-sdk/react";
import type { Message } from "@langchain/langgraph-sdk";
import {
  uiMessageReducer,
  isUIMessage,
  isRemoveUIMessage,
  type UIMessage,
  type RemoveUIMessage,
} from "@langchain/langgraph-sdk/react-ui";
import { useQueryState } from "nuqs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LangGraphLogoSVG } from "@/components/icons/langgraph";
import { Label } from "@/components/ui/label";
import { ArrowRight } from "lucide-react";
import { PasswordInput } from "@/components/ui/password-input";
import { getApiKey } from "@/lib/api-key";
import { logClient } from "@/lib/client-logger";
import { listAssistants } from "@/lib/platform-api/assistants";
import { listEnvironmentMappings } from "@/lib/platform-api/environment-mappings";
import { isJwtToken } from "@/lib/token";
import { useThreads } from "./Thread";
import { useWorkspaceContext } from "./WorkspaceContext";
import { toast } from "sonner";

export type StateType = { messages: Message[]; ui?: UIMessage[] };

const useTypedStream = useStream<
  StateType,
  {
    UpdateType: {
      messages?: Message[] | Message | string;
      ui?: (UIMessage | RemoveUIMessage)[] | UIMessage | RemoveUIMessage;
      context?: Record<string, unknown>;
    };
    CustomEventType: UIMessage | RemoveUIMessage;
  }
>;

type StreamContextType = ReturnType<typeof useTypedStream>;
const StreamContext = createContext<StreamContextType | undefined>(undefined);

async function sleep(ms = 4000) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function checkGraphStatus(
  apiUrl: string,
  authHeaders: Record<string, string>,
): Promise<boolean> {
  try {
    const res = await fetch(`${apiUrl}/info`, {
      headers: authHeaders,
    });

    return res.ok;
  } catch (e) {
    await logClient({
      level: "error",
      event: "stream_check_graph_status_error",
      message: "Failed to check graph status",
      context: {
        apiUrl,
        error: String(e),
      },
    });
    return false;
  }
}

async function fetchAutoToken(): Promise<string | null> {
  try {
    const res = await fetch("/api/keycloak-token", {
      method: "GET",
      cache: "no-store",
    });
    if (!res.ok) {
      return null;
    }

    const payload = (await res.json()) as { access_token?: string };
    if (!payload.access_token) {
      return null;
    }
    return payload.access_token;
  } catch (error) {
    await logClient({
      level: "error",
      event: "stream_auto_token_fetch_error",
      message: "Failed to fetch auto token",
      context: {
        error: String(error),
      },
    });
    return null;
  }
}

const StreamSession = ({
  children,
  apiKey,
  apiUrl,
  assistantId,
  tenantId,
  projectId,
  autoTokenEnabled,
}: {
  children: ReactNode;
  apiKey: string | null;
  apiUrl: string;
  assistantId: string;
  tenantId: string;
  projectId: string;
  autoTokenEnabled: boolean;
}) => {
  const [threadId, setThreadId] = useQueryState("threadId");
  const { getThreads, setThreads } = useThreads();
  const runtimeHeaders = useMemo<Record<string, string>>(
    () => ({
      ...(tenantId ? { "x-tenant-id": tenantId } : {}),
      ...(projectId ? { "x-project-id": projectId } : {}),
    }),
    [tenantId, projectId],
  );

  const authHeaders = useMemo<Record<string, string>>(() => {
    if (isJwtToken(apiKey)) {
      return {
        Authorization: `Bearer ${apiKey}`,
        ...runtimeHeaders,
      };
    }

    if (apiKey && !autoTokenEnabled) {
      return {
        "X-Api-Key": apiKey,
        ...runtimeHeaders,
      };
    }

    return runtimeHeaders;
  }, [apiKey, runtimeHeaders, autoTokenEnabled]);

  const streamApiKey = isJwtToken(apiKey) ? undefined : apiKey ?? undefined;

  const streamValue = useTypedStream({
    apiUrl,
    apiKey: streamApiKey,
    defaultHeaders: authHeaders,
    assistantId,
    threadId: threadId ?? null,
    fetchStateHistory: true,
    onCustomEvent: (event, options) => {
      if (isUIMessage(event) || isRemoveUIMessage(event)) {
        options.mutate((prev) => {
          const ui = uiMessageReducer(prev.ui ?? [], event);
          return { ...prev, ui };
        });
      }
    },
    onThreadId: (id) => {
      setThreadId(id);
      logClient({
        level: "info",
        event: "stream_thread_id_changed",
        message: "Thread id updated from stream callback",
        context: {
          threadId: id,
          assistantId,
        },
      });
      sleep().then(() =>
        getThreads()
          .then(setThreads)
          .catch((error) =>
            logClient({
              level: "error",
              event: "stream_refresh_threads_error",
              message: "Failed to refresh threads after thread id change",
              context: {
                threadId: id,
                error: String(error),
              },
            }),
          ),
      );
    },
  });

  useEffect(() => {
    checkGraphStatus(apiUrl, authHeaders).then((ok) => {
      if (!ok) {
        logClient({
          level: "warn",
          event: "stream_graph_status_unhealthy",
          message: "Graph status check failed",
          context: {
            apiUrl,
            assistantId,
          },
        });
        toast.error("Failed to connect to LangGraph server", {
          description: () => (
            <p>
              Please ensure your graph is running at <code>{apiUrl}</code> and
              your API key is correctly set (if connecting to a deployed graph).
            </p>
          ),
          duration: 10000,
          richColors: true,
          closeButton: true,
        });
      }
    });
  }, [apiUrl, assistantId, authHeaders]);

  return (
    <StreamContext.Provider value={streamValue}>
      {children}
    </StreamContext.Provider>
  );
};

// Default values for the form
const DEFAULT_API_URL = "http://localhost:2024";
const DEFAULT_ASSISTANT_ID = "assistant";
const DEFAULT_RUNTIME_ENV = process.env.NEXT_PUBLIC_RUNTIME_ENV ?? "dev";

function normalizeApiUrl(apiUrl: string, fallbackApiUrl?: string): string {
  if (apiUrl.includes(":8123")) {
    return fallbackApiUrl || DEFAULT_API_URL;
  }
  return apiUrl;
}

export const StreamProvider: FC<{ children: ReactNode }> = ({
  children,
}) => {
  const { tenantId, projectId, assistantId: selectedAssistantId, setAssistantId: setSelectedAssistantId } =
    useWorkspaceContext();
  const autoTokenEnabled = process.env.NEXT_PUBLIC_AUTO_KEYCLOAK_TOKEN === "true";

  // Get environment variables
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined =
    process.env.NEXT_PUBLIC_ASSISTANT_ID;

  // Use URL params with env var fallbacks
  const [apiUrl, setApiUrl] = useQueryState("apiUrl", {
    defaultValue: envApiUrl || "",
  });
  const [assistantId, setAssistantId] = useQueryState("assistantId", {
    defaultValue: envAssistantId || "",
  });

  // For API key, use localStorage with env var fallback
  const [apiKey, _setApiKey] = useState(() => {
    const storedKey = getApiKey();
    return storedKey || "";
  });
  const [autoTokenReady, setAutoTokenReady] = useState(!autoTokenEnabled);

  const setApiKey = useCallback((key: string) => {
    window.localStorage.setItem("lg:chat:apiKey", key);
    _setApiKey(key);
  }, []);

  useEffect(() => {
    if (!envAssistantId && assistantId === "agent") {
      setAssistantId(DEFAULT_ASSISTANT_ID);
      logClient({
        level: "warn",
        event: "stream_assistant_id_migrated",
        message: "Migrated legacy assistantId 'agent' to 'assistant'",
      });
    }
  }, [assistantId, envAssistantId, setAssistantId]);

  useEffect(() => {
    if (!apiUrl) {
      return;
    }
    window.localStorage.setItem("lg:chat:apiUrl", apiUrl);
  }, [apiUrl]);

  useEffect(() => {
    if (!apiUrl) {
      return;
    }

    if (apiUrl.includes(":8123")) {
      setApiUrl(DEFAULT_API_URL);
      logClient({
        level: "warn",
        event: "stream_runtime_url_rewritten",
        message: "Rewrote direct runtime URL to proxy URL for CORS-safe browser access",
        context: {
          from: apiUrl,
          to: DEFAULT_API_URL,
        },
      });
    }
  }, [apiUrl, setApiUrl]);

  useEffect(() => {
    let cancelled = false;

    async function syncExecutionTargetFromProjectScope() {
      if (!projectId) {
        return;
      }

      try {
        let resolvedAssistantId = selectedAssistantId;
        let resolvedGraphId: string | null = null;

        if (!resolvedAssistantId) {
          const assistants = await listAssistants(projectId, { limit: 1, sortBy: "created_at", sortOrder: "desc" });
          if (cancelled || assistants.length === 0) {
            return;
          }
          resolvedAssistantId = assistants[0].id;
          resolvedGraphId = assistants[0].graph_id;
          setSelectedAssistantId(resolvedAssistantId);
        }

        const bindings = await listEnvironmentMappings(resolvedAssistantId, {
          limit: 100,
          sortBy: "environment",
          sortOrder: "asc",
        });
        if (cancelled) {
          return;
        }

        const preferredBinding =
          bindings.find((item) => item.environment === DEFAULT_RUNTIME_ENV) ?? bindings[0] ?? null;

        if (preferredBinding) {
          resolvedGraphId = preferredBinding.langgraph_assistant_id;
        }

        if (resolvedGraphId && resolvedGraphId !== assistantId) {
          setAssistantId(resolvedGraphId);
        }
      } catch (error) {
        if (!cancelled) {
          logClient({
            level: "warn",
            event: "stream_scope_autolink_failed",
            message: "Failed to auto-link chat target from project scope",
            context: {
              projectId,
              selectedAssistantId,
              error: String(error),
            },
          });
        }
      }
    }

    void syncExecutionTargetFromProjectScope();

    return () => {
      cancelled = true;
    };
  }, [projectId, selectedAssistantId, assistantId, setSelectedAssistantId, setAssistantId]);

  useEffect(() => {
    if (!autoTokenEnabled) {
      return;
    }

    let cancelled = false;
    setAutoTokenReady(false);

    fetchAutoToken().then((token) => {
      if (cancelled) {
        return;
      }

      if (token) {
        setApiKey(token);
        logClient({
          level: "info",
          event: "stream_auto_token_loaded",
          message: "Loaded token in auto mode",
        });
      }

      setAutoTokenReady(true);
    });

    return () => {
      cancelled = true;
    };
  }, [autoTokenEnabled, setApiKey]);

  useEffect(() => {
    if (!autoTokenEnabled) {
      return;
    }

    const id = window.setInterval(() => {
      fetchAutoToken().then((token) => {
        if (!token) {
          return;
        }
        _setApiKey((prev) => {
          if (prev === token) {
            return prev;
          }
          window.localStorage.setItem("lg:chat:apiKey", token);
          logClient({
            level: "info",
            event: "stream_auto_token_refreshed",
            message: "Refreshed token in auto mode",
          });
          return token;
        });
      });
    }, 5 * 60 * 1000);

    return () => {
      window.clearInterval(id);
    };
  }, [autoTokenEnabled]);

  // Determine final values to use, prioritizing URL params then env vars
  const finalApiUrl = normalizeApiUrl(apiUrl || envApiUrl || "", envApiUrl);
  const finalAssistantId = assistantId || envAssistantId;

  if (autoTokenEnabled && !autoTokenReady) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="text-muted-foreground text-sm">Loading authentication...</div>
      </div>
    );
  }

  // Show the form if we: don't have an API URL, or don't have an assistant ID
  if (!finalApiUrl || !finalAssistantId) {
    return (
      <div className="flex min-h-screen w-full items-center justify-center p-4">
        <div className="animate-in fade-in-0 zoom-in-95 bg-background flex max-w-3xl flex-col rounded-lg border shadow-lg">
          <div className="mt-14 flex flex-col gap-2 border-b p-6">
            <div className="flex flex-col items-start gap-2">
              <LangGraphLogoSVG className="h-7" />
              <h1 className="text-xl font-semibold tracking-tight">
                Agent Chat
              </h1>
            </div>
            <p className="text-muted-foreground">
              Welcome to Agent Chat! Before you get started, you need to enter
              the URL of the deployment and the assistant / graph ID.
            </p>
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();

              const form = e.target as HTMLFormElement;
              const formData = new FormData(form);
              const apiUrl = formData.get("apiUrl") as string;
              const assistantId = formData.get("assistantId") as string;
              const apiKey = formData.get("apiKey") as string;

              setApiUrl(apiUrl);
              setApiKey(apiKey);
              setAssistantId(assistantId);

              form.reset();
            }}
            className="bg-muted/50 flex flex-col gap-6 p-6"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="apiUrl">
                Deployment URL<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the URL of your LangGraph deployment. Can be a local, or
                production deployment.
              </p>
              <Input
                id="apiUrl"
                name="apiUrl"
                className="bg-background"
                defaultValue={apiUrl || DEFAULT_API_URL}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="assistantId">
                Assistant / Graph ID<span className="text-rose-500">*</span>
              </Label>
              <p className="text-muted-foreground text-sm">
                This is the ID of the graph (can be the graph name), or
                assistant to fetch threads from, and invoke when actions are
                taken.
              </p>
              <Input
                id="assistantId"
                name="assistantId"
                className="bg-background"
                defaultValue={assistantId || DEFAULT_ASSISTANT_ID}
                required
              />
            </div>

            <div className="flex flex-col gap-2">
              <Label htmlFor="apiKey">LangSmith API Key</Label>
              <p className="text-muted-foreground text-sm">
                This is <strong>NOT</strong> required if using a local LangGraph
                server. This value is stored in your browser's local storage and
                is only used to authenticate requests sent to your LangGraph
                server.
              </p>
              {autoTokenEnabled ? (
                <p className="text-xs text-emerald-700">
                  Auto token mode is enabled. Keycloak token is fetched from
                  <code> /api/keycloak-token</code> automatically.
                </p>
              ) : null}
              <PasswordInput
                id="apiKey"
                name="apiKey"
                defaultValue={apiKey ?? ""}
                className="bg-background"
                placeholder="lsv2_pt_..."
              />
            </div>

            <div className="mt-2 flex justify-end">
              <Button
                type="submit"
                size="lg"
              >
                Continue
                <ArrowRight className="size-5" />
              </Button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return (
    <StreamSession
      apiKey={apiKey}
      apiUrl={finalApiUrl}
      assistantId={finalAssistantId}
      tenantId={tenantId}
      projectId={projectId}
      autoTokenEnabled={autoTokenEnabled}
    >
      {children}
    </StreamSession>
  );
};

// Create a custom hook to use the context
export const useStreamContext = (): StreamContextType => {
  const context = useContext(StreamContext);
  if (context === undefined) {
    throw new Error("useStreamContext must be used within a StreamProvider");
  }
  return context;
};

export default StreamContext;
