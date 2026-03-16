import { apiFetch } from "./client";
import type { AgentSummary, AgentDetail, AgentCostConfig } from "./types";

export async function listAgents(): Promise<AgentSummary[]> {
  return apiFetch("/api/v1/agents");
}

export async function getAgent(agentId: string): Promise<AgentDetail> {
  return apiFetch(`/api/v1/agents/${agentId}`);
}

export async function upsertCostConfig(
  agentId: string,
  config: Omit<AgentCostConfig, "updated_at">
): Promise<AgentCostConfig> {
  return apiFetch(`/api/v1/agents/${agentId}/cost-config`, {
    method: "PUT",
    body: JSON.stringify(config),
  });
}

export async function getCostConfig(
  agentId: string
): Promise<AgentCostConfig> {
  return apiFetch(`/api/v1/agents/${agentId}/cost-config`);
}
