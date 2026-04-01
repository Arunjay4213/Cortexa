import { apiFetch } from "./client";
import type {
  CounterfactualStageRequest,
  CounterfactualResult,
} from "./types";

export async function stageCounterfactual(
  request: CounterfactualStageRequest
): Promise<CounterfactualResult> {
  return apiFetch("/api/v1/counterfactual/stage", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getSession(
  session_id: string
): Promise<CounterfactualResult> {
  return apiFetch(`/api/v1/counterfactual/${session_id}`);
}

export async function commitSession(
  session_id: string
): Promise<{ status: string; session_id: string }> {
  return apiFetch(`/api/v1/counterfactual/${session_id}/commit`, {
    method: "POST",
  });
}

export async function discardSession(
  session_id: string
): Promise<{ status: string; session_id: string }> {
  return apiFetch(`/api/v1/counterfactual/${session_id}`, {
    method: "DELETE",
  });
}
