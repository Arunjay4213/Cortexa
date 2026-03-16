import { apiFetch } from "./client";
import type {
  AttributionScore,
  MemoryProfile,
  ExactAttributionResult,
} from "./types";

export async function getAttributionByTransaction(
  txnId: string
): Promise<AttributionScore[]> {
  return apiFetch(`/api/v1/attribution/${txnId}`);
}

export async function getAttributionByMemory(
  memoryId: string
): Promise<{ scores: AttributionScore[]; profile: MemoryProfile | null }> {
  return apiFetch(`/api/v1/attribution/memory/${memoryId}`);
}

export async function triggerExactAttribution(
  txnId: string
): Promise<ExactAttributionResult> {
  return apiFetch(`/api/v1/attribution/${txnId}/exact`, {
    method: "POST",
  });
}
