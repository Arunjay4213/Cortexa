import useSWR from "swr";
import { listAgents, getAgent } from "@/lib/api/agents";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import type { AgentSummary, AgentDetail } from "@/lib/api/types";

export function useAgents() {
  const { connected } = useWebSocket();
  return useSWR<AgentSummary[]>("/agents", listAgents, {
    refreshInterval: connected ? 0 : 10000,
    revalidateOnFocus: true,
    dedupingInterval: 2000,
  });
}

export function useAgent(agentId: string | null) {
  const { connected } = useWebSocket();
  return useSWR<AgentDetail>(
    agentId ? `/agents/${agentId}` : null,
    () => getAgent(agentId!),
    { refreshInterval: connected ? 0 : 10000, revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}
