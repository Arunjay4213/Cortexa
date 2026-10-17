import { apiFetch } from "./client";
import type {
  ContaminationScanResponse,
  GateCheckResponse,
  QuarantineSimulationResponse,
} from "./types";

export async function scanContamination(
  agent_id: string,
  transaction_window?: number
): Promise<ContaminationScanResponse> {
  return apiFetch("/api/v1/grounding/scan", {
    method: "POST",
    body: JSON.stringify({ agent_id, transaction_window }),
  });
}

export async function gateCheckMemory(
  agent_id: string,
  content: string,
  embedding?: number[] | null,
  source_type?: string
): Promise<GateCheckResponse> {
  return apiFetch("/api/v1/grounding/gate", {
    method: "POST",
    body: JSON.stringify({ agent_id, content, embedding, source_type }),
  });
}

export async function quarantineSimulation(
  agent_id: string,
  memory_ids: string[],
  transaction_window?: number
): Promise<QuarantineSimulationResponse> {
  return apiFetch("/api/v1/grounding/quarantine", {
    method: "POST",
    body: JSON.stringify({ agent_id, memory_ids, transaction_window }),
  });
}
