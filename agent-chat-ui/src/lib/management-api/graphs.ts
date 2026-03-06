import { createManagementApiClient } from "./client";

export type ManagementGraph = {
  graph_id: string;
  description?: string;
};

type GraphListResponse = {
  items: ManagementGraph[];
  total: number;
  limit: number;
  offset: number;
};

export async function listGraphsPage(
  projectId: string,
  options?: { limit?: number; offset?: number; query?: string },
): Promise<GraphListResponse> {
  const client = createManagementApiClient({
    requireAuth: false,
    headers: projectId ? { "x-project-id": projectId } : {},
  });
  if (!client) {
    return { items: [], total: 0, limit: options?.limit ?? 20, offset: options?.offset ?? 0 };
  }

  return client.post<GraphListResponse>("/api/langgraph/graphs/search", {
    limit: options?.limit ?? 20,
    offset: options?.offset ?? 0,
    query: options?.query?.trim() || undefined,
  });
}
