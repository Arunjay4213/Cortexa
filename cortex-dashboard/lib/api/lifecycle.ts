import { apiFetch } from "./client";
import type {
  LifecycleRecommendations,
  BudgetOptimization,
  ExecuteRecommendationsRequest,
  ExecuteRecommendationsResponse,
} from "./types";

export async function getRecommendations(
  agentId: string
): Promise<LifecycleRecommendations> {
  return apiFetch(`/api/v1/lifecycle/${agentId}/recommendations`);
}

export async function executeRecommendations(
  agentId: string,
  req: ExecuteRecommendationsRequest
): Promise<ExecuteRecommendationsResponse> {
  return apiFetch(`/api/v1/lifecycle/${agentId}/execute`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getBudgetOptimization(
  agentId: string,
  budgetTokens = 100000
): Promise<BudgetOptimization> {
  return apiFetch(
    `/api/v1/lifecycle/${agentId}/budget?budget_tokens=${budgetTokens}`
  );
}
