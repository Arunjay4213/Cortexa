import useSWR from "swr";
import { listSnapshots, diffSnapshots, listBranches } from "@/lib/api/snapshots";
import type { SnapshotResponse, SnapshotDiff, BranchResponse } from "@/lib/api/types";

export function useSnapshots(agentId: string | null) {
  return useSWR<SnapshotResponse[]>(
    agentId ? `/snapshots/${agentId}` : null,
    () => listSnapshots(agentId!),
    { revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}

export function useSnapshotDiff(
  agentId: string | null,
  id1: string | null,
  id2: string | null
) {
  return useSWR<SnapshotDiff>(
    agentId && id1 && id2
      ? `/snapshots/${agentId}/${id1}/diff/${id2}`
      : null,
    () => diffSnapshots(agentId!, id1!, id2!),
    { revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}

export function useBranches(agentId: string | null) {
  return useSWR<BranchResponse[]>(
    agentId ? `/branches/${agentId}` : null,
    () => listBranches(agentId!),
    { revalidateOnFocus: true, dedupingInterval: 2000 }
  );
}
