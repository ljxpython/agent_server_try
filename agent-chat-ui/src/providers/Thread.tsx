import { validate } from "uuid";
import { getApiKey } from "@/lib/api-key";
import { logClient } from "@/lib/client-logger";
import { isJwtToken } from "@/lib/token";
import type { Thread } from "@langchain/langgraph-sdk";
import { useQueryState } from "nuqs";
import {
  type Dispatch,
  type ReactNode,
  type SetStateAction,
  createContext,
  useCallback,
  useContext,
  useState,
} from "react";
import { createClient } from "./client";
import { useWorkspaceContext } from "./WorkspaceContext";

const DEFAULT_PROXY_API_URL = "http://localhost:2024";

function normalizeApiUrl(apiUrl: string, fallbackApiUrl?: string): string {
  if (apiUrl.includes(":8123")) {
    return fallbackApiUrl || DEFAULT_PROXY_API_URL;
  }
  return apiUrl;
}

interface ThreadContextType {
  getThreads: () => Promise<Thread[]>;
  threads: Thread[];
  setThreads: Dispatch<SetStateAction<Thread[]>>;
  threadsLoading: boolean;
  setThreadsLoading: Dispatch<SetStateAction<boolean>>;
}

const ThreadContext = createContext<ThreadContextType | undefined>(undefined);

function getThreadSearchMetadata(
  assistantId: string,
): { graph_id: string } | { assistant_id: string } {
  if (validate(assistantId)) {
    return { assistant_id: assistantId };
  } else {
    return { graph_id: assistantId };
  }
}

export function ThreadProvider({ children }: { children: ReactNode }) {
  const { tenantId, projectId } = useWorkspaceContext();
  const autoTokenEnabled = process.env.NEXT_PUBLIC_AUTO_KEYCLOAK_TOKEN === "true";
  const envApiUrl: string | undefined = process.env.NEXT_PUBLIC_API_URL;
  const envAssistantId: string | undefined = process.env.NEXT_PUBLIC_ASSISTANT_ID;

  const [apiUrl] = useQueryState("apiUrl");
  const [assistantId] = useQueryState("assistantId");
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadsLoading, setThreadsLoading] = useState(false);

  const getThreads = useCallback(async (): Promise<Thread[]> => {
    const finalApiUrl = normalizeApiUrl(apiUrl || envApiUrl || "", envApiUrl);
    const finalAssistantId = assistantId || envAssistantId;
    if (!finalApiUrl || !finalAssistantId) return [];

    const rawApiKey = getApiKey();
    const clientApiKey =
      rawApiKey && (!autoTokenEnabled || isJwtToken(rawApiKey))
        ? rawApiKey
        : undefined;

    const client = createClient(finalApiUrl, clientApiKey, {
      ...(tenantId ? { "x-tenant-id": tenantId } : {}),
      ...(projectId ? { "x-project-id": projectId } : {}),
    });

    try {
      const threads = await client.threads.search({
        metadata: {
          ...getThreadSearchMetadata(finalAssistantId),
        },
        limit: 100,
      });

      logClient({
        level: "debug",
        event: "thread_list_loaded",
        message: "Loaded threads list",
        context: {
          assistantId: finalAssistantId,
          count: threads.length,
        },
      });

      return threads;
    } catch (error) {
      logClient({
        level: "error",
        event: "thread_list_load_error",
        message: "Failed to load threads list",
        context: {
          assistantId: finalAssistantId,
          apiUrl: finalApiUrl,
          error: String(error),
        },
      });
      throw error;
    }
  }, [apiUrl, assistantId, envApiUrl, envAssistantId, tenantId, projectId, autoTokenEnabled]);

  const value = {
    getThreads,
    threads,
    setThreads,
    threadsLoading,
    setThreadsLoading,
  };

  return (
    <ThreadContext.Provider value={value}>{children}</ThreadContext.Provider>
  );
}

export function useThreads() {
  const context = useContext(ThreadContext);
  if (context === undefined) {
    throw new Error("useThreads must be used within a ThreadProvider");
  }
  return context;
}
