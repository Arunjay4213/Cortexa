import useSWR from "swr";
import { listMemories, getMemory, searchMemories } from "@/lib/api/memories";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type { MemoryUnit, PaginatedResponse, MemorySearchResult } from "@/lib/api/types";

export function useMemories(params?: {
  agent_id?: string;
  tier?: string;
  sort_by?: string;
  order?: string;
  offset?: number;
  limit?: number;
}) {
  const { connected } = useWebSocket();
  const key = params
    ? `/memories?${JSON.stringify(params)}`
    : "/memories";
  return useSWR<PaginatedResponse<MemoryUnit>>(key, () => listMemories(params), {
    refreshInterval: connected ? 0 : 10000,
    revalidateOnFocus: true,
    dedupingInterval: 2000,
  });
}

export function useMemory(id: string | null) {
  return useSWR(
    id ? `/memories/${id}` : null,
    () => getMemory(id!),
    { revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}

export function useMemorySearch(query: string | null, agentId?: string) {
  return useSWR<MemorySearchResult[]>(
    query ? `/memories/search?q=${query}&agent_id=${agentId || ""}` : null,
    () => searchMemories({ q: query!, agent_id: agentId }),
    { dedupingInterval: 2000 }
  );
}
