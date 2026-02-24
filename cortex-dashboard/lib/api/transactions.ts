import { apiFetch } from "./client";
import type {
  Transaction,
  TransactionWithScores,
  PaginatedResponse,
  AttributionScore,
} from "./types";

export async function listTransactions(params?: {
  agent_id?: string;
  status?: string;
  offset?: number;
  limit?: number;
}): Promise<PaginatedResponse<Transaction>> {
  const query = new URLSearchParams();
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  if (params?.status) query.set("status", params.status);
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  return apiFetch(`/api/v1/transactions?${query}`);
}

export async function getTransaction(
  txnId: string
): Promise<{ transaction: Transaction; scores: AttributionScore[] }> {
  return apiFetch(`/api/v1/transactions/${txnId}`);
}

export async function createTransaction(body: {
  query_text: string;
  response_text: string;
  retrieved_memory_ids: string[];
  agent_id?: string;
  model?: string;
}): Promise<TransactionWithScores> {
  return apiFetch("/api/v1/transactions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
