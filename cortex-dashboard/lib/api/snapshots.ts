import { apiFetch } from "./client";
import type {
  SnapshotResponse,
  SnapshotEntryResponse,
  SnapshotDiff,
  BranchResponse,
} from "./types";

export async function createSnapshot(
  agentId: string,
  body: { name: string; description?: string; created_by?: string }
): Promise<SnapshotResponse> {
  return apiFetch(`/api/v1/snapshots/${agentId}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listSnapshots(agentId: string): Promise<SnapshotResponse[]> {
  return apiFetch(`/api/v1/snapshots/${agentId}`);
}

export async function getSnapshot(
  agentId: string,
  snapshotId: string
): Promise<{ snapshot: SnapshotResponse; entries: SnapshotEntryResponse[] }> {
  return apiFetch(`/api/v1/snapshots/${agentId}/${snapshotId}`);
}

export async function diffSnapshots(
  agentId: string,
  id1: string,
  id2: string
): Promise<SnapshotDiff> {
  return apiFetch(`/api/v1/snapshots/${agentId}/${id1}/diff/${id2}`);
}

export async function restoreSnapshot(
  agentId: string,
  snapshotId: string
): Promise<{ restored_from: string; agent_id: string; memory_count: number }> {
  return apiFetch(`/api/v1/snapshots/${agentId}/${snapshotId}/restore`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export async function createBranch(
  agentId: string,
  body: { name: string; snapshot_id: string; description?: string }
): Promise<BranchResponse> {
  return apiFetch(`/api/v1/branches/${agentId}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function listBranches(agentId: string): Promise<BranchResponse[]> {
  return apiFetch(`/api/v1/branches/${agentId}`);
}
