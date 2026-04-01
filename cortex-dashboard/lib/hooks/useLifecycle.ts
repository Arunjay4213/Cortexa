import useSWR from "swr";
import {
  getRecommendations,
  getBudgetOptimization,
} from "@/lib/api/lifecycle";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type {
  LifecycleRecommendations,
  BudgetOptimization,
} from "@/lib/api/types";

export function useLifecycleRecommendations(agentId: string | null) {
  const { connected } = useWebSocket();
  return useSWR<LifecycleRecommendations>(
    agentId ? `/lifecycle/${agentId}/recommendations` : null,
    () => getRecommendations(agentId!),
    { refreshInterval: connected ? 0 : 10000, revalidateOnFocus: false, dedupingInterval: 5000 }
  );
}

export function useBudgetOptimization(
  agentId: string | null,
  budgetTokens = 100000
) {
  const { connected } = useWebSocket();
  return useSWR<BudgetOptimization>(
    agentId ? `/lifecycle/${agentId}/budget?tokens=${budgetTokens}` : null,
    () => getBudgetOptimization(agentId!, budgetTokens),
    { refreshInterval: connected ? 0 : 10000, revalidateOnFocus: false, dedupingInterval: 5000 }
  );
}
