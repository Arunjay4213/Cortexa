import useSWR from "swr";
import { listTransactions, getTransaction } from "@/lib/api/transactions";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type { Transaction, PaginatedResponse, AttributionScore } from "@/lib/api/types";

export function useTransactions(params?: {
  agent_id?: string;
  status?: string;
  offset?: number;
  limit?: number;
}) {
  const { connected } = useWebSocket();
  const key = params
    ? `/transactions?${JSON.stringify(params)}`
    : "/transactions";
  return useSWR<PaginatedResponse<Transaction>>(key, () => listTransactions(params), {
    refreshInterval: connected ? 0 : 10000,
    revalidateOnFocus: true,
    dedupingInterval: 2000,
  });
}

export function useTransaction(id: string | null) {
  return useSWR<{ transaction: Transaction; scores: AttributionScore[] }>(
    id ? `/transactions/${id}` : null,
    () => getTransaction(id!),
    { revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}
