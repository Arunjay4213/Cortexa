import { apiFetch } from "./client";
import type {
  Contradiction,
  ContradictionDetectionResult,
  HealthSnapshot,
} from "./types";

export async function getHealthSnapshots(
  agentId: string
): Promise<HealthSnapshot[]> {
  return apiFetch(`/api/v1/health/${agentId}`);
}

export async function listContradictions(params?: {
  resolved?: boolean;
  agent_id?: string;
}): Promise<Contradiction[]> {
  const query = new URLSearchParams();
  if (params?.resolved !== undefined)
    query.set("resolved", String(params.resolved));
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  return apiFetch(`/api/v1/health/contradictions?${query}`);
}

export async function detectContradictions(
  agentId?: string
): Promise<ContradictionDetectionResult> {
  const query = agentId ? `?agent_id=${agentId}` : "";
  return apiFetch(`/api/v1/health/contradictions/detect${query}`, {
    method: "POST",
  });
}

export async function resolveContradiction(
  id: string,
  resolvedBy?: string
): Promise<{ id: string; resolved: boolean; resolved_by: string }> {
  const query = resolvedBy ? `?resolved_by=${resolvedBy}` : "";
  return apiFetch(`/api/v1/health/contradictions/${id}/resolve${query}`, {
    method: "PATCH",
  });
}
