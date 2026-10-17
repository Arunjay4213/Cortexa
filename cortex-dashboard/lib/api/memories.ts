import { apiFetch } from "./client";
import type {
  MemoryUnit,
  MemoryCreate,
  MemoryUpdate,
  MemorySearchResult,
  PaginatedResponse,
} from "./types";

export async function listMemories(params?: {
  agent_id?: string;
  tier?: string;
  sort_by?: string;
  order?: string;
  offset?: number;
  limit?: number;
}): Promise<PaginatedResponse<MemoryUnit>> {
  const query = new URLSearchParams();
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  if (params?.tier) query.set("tier", params.tier);
  if (params?.sort_by) query.set("sort_by", params.sort_by);
  if (params?.order) query.set("order", params.order);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  return apiFetch(`/api/v1/memories?${query}`);
}

export async function getMemory(
  memoryId: string
): Promise<{ memory: MemoryUnit; profile: unknown }> {
  return apiFetch(`/api/v1/memories/${memoryId}`);
}

export async function createMemory(body: MemoryCreate): Promise<MemoryUnit> {
  return apiFetch("/api/v1/memories", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateMemory(
  memoryId: string,
  body: MemoryUpdate
): Promise<MemoryUnit> {
  return apiFetch(`/api/v1/memories/${memoryId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function deleteMemory(memoryId: string): Promise<void> {
  return apiFetch(`/api/v1/memories/${memoryId}`, { method: "DELETE" });
}

export async function searchMemories(params: {
  q: string;
  agent_id?: string;
  top_k?: number;
}): Promise<MemorySearchResult[]> {
  const query = new URLSearchParams({ q: params.q });
  if (params.agent_id) query.set("agent_id", params.agent_id);
  if (params.top_k !== undefined) query.set("top_k", String(params.top_k));
  return apiFetch(`/api/v1/memories/search?${query}`);
}
