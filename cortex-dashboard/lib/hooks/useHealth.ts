import useSWR from "swr";
import { getHealthSnapshots, listContradictions } from "@/lib/api/health";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type { HealthSnapshot, Contradiction } from "@/lib/api/types";

export function useHealthSnapshots(agentId: string | null) {
  const { connected } = useWebSocket();
  return useSWR<HealthSnapshot[]>(
    agentId ? `/health/${agentId}` : null,
    () => getHealthSnapshots(agentId!),
    { refreshInterval: connected ? 0 : 10000, dedupingInterval: 2000 }
  );
}

export function useContradictions(params?: {
  resolved?: boolean;
  agent_id?: string;
}) {
  const { connected } = useWebSocket();
  const key = params
    ? `/health/contradictions?${JSON.stringify(params)}`
    : "/health/contradictions";
  return useSWR<Contradiction[]>(key, () => listContradictions(params), {
    refreshInterval: connected ? 0 : 10000,
    revalidateOnFocus: true,
    dedupingInterval: 2000,
  });
}
