import useSWR from "swr";
import {
  getDashboardOverview,
  getTimeSeries,
  getTopMemories,
  getCostSummary,
} from "@/lib/api/dashboard";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type {
  DashboardOverview,
  TimeSeriesResponse,
  TopMemoryResponse,
  CostSummaryResponse,
} from "@/lib/api/types";

export function useDashboardOverview() {
  const { connected } = useWebSocket();
  return useSWR<DashboardOverview>("/dashboard/overview", getDashboardOverview, {
    refreshInterval: connected ? 0 : 10000,
    revalidateOnFocus: true,
    dedupingInterval: 2000,
  });
}

export function useTimeSeries(params?: {
  agent_id?: string;
  metric?: string;
  days?: number;
  bucket?: string;
}) {
  const { connected } = useWebSocket();
  const key = params
    ? `/dashboard/timeseries?${JSON.stringify(params)}`
    : "/dashboard/timeseries";
  return useSWR<TimeSeriesResponse>(key, () => getTimeSeries(params), {
    refreshInterval: connected ? 0 : 10000,
    dedupingInterval: 2000,
  });
}

export function useTopMemories(params?: { agent_id?: string; n?: number }) {
  const { connected } = useWebSocket();
  const key = params
    ? `/dashboard/top-memories?${JSON.stringify(params)}`
    : "/dashboard/top-memories";
  return useSWR<TopMemoryResponse[]>(key, () => getTopMemories(params), {
    refreshInterval: connected ? 0 : 10000,
    dedupingInterval: 2000,
  });
}

export function useCostSummary(params?: {
  agent_id?: string;
  days?: number;
}) {
  const { connected } = useWebSocket();
  const key = params
    ? `/dashboard/cost-summary?${JSON.stringify(params)}`
    : "/dashboard/cost-summary";
  return useSWR<CostSummaryResponse[]>(key, () => getCostSummary(params), {
    refreshInterval: connected ? 0 : 10000,
    dedupingInterval: 2000,
  });
}
