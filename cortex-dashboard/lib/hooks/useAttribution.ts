import useSWR from "swr";
import {
  getAttributionByTransaction,
  getAttributionByMemory,
} from "@/lib/api/attribution";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type { AttributionScore, MemoryProfile } from "@/lib/api/types";

export function useAttributionByTransaction(txnId: string | null) {
  const { connected } = useWebSocket();
  return useSWR<AttributionScore[]>(
    txnId ? `/attribution/${txnId}` : null,
    () => getAttributionByTransaction(txnId!),
    { refreshInterval: connected ? 0 : 10000, revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}

export function useAttributionByMemory(memoryId: string | null) {
  const { connected } = useWebSocket();
  return useSWR<{ scores: AttributionScore[]; profile: MemoryProfile | null }>(
    memoryId ? `/attribution/memory/${memoryId}` : null,
    () => getAttributionByMemory(memoryId!),
    { refreshInterval: connected ? 0 : 10000, revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}
