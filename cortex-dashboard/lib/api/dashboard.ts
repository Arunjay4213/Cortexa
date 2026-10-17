import { apiFetch } from "./client";
import type {
  DashboardOverview,
  TimeSeriesResponse,
  TopMemoryResponse,
  CostSummaryResponse,
} from "./types";

export async function getDashboardOverview(): Promise<DashboardOverview> {
  return apiFetch("/api/v1/dashboard/overview");
}

export async function getTimeSeries(params?: {
  agent_id?: string;
  metric?: string;
  days?: number;
  bucket?: string;
}): Promise<TimeSeriesResponse> {
  const query = new URLSearchParams();
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  if (params?.metric) query.set("metric", params.metric);
  if (params?.days !== undefined) query.set("days", String(params.days));
  if (params?.bucket) query.set("bucket", params.bucket);
  return apiFetch(`/api/v1/dashboard/metrics/timeseries?${query}`);
}

export async function getTopMemories(params?: {
  agent_id?: string;
  n?: number;
}): Promise<TopMemoryResponse[]> {
  const query = new URLSearchParams();
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  if (params?.n !== undefined) query.set("n", String(params.n));
  return apiFetch(`/api/v1/dashboard/top-memories?${query}`);
}

export async function getCostSummary(params?: {
  agent_id?: string;
  days?: number;
}): Promise<CostSummaryResponse[]> {
  const query = new URLSearchParams();
  if (params?.agent_id) query.set("agent_id", params.agent_id);
  if (params?.days !== undefined) query.set("days", String(params.days));
  return apiFetch(`/api/v1/dashboard/cost-summary?${query}`);
}
