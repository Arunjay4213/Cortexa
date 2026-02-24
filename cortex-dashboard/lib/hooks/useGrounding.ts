import useSWR from "swr";
import { scanContamination } from "@/lib/api/grounding";
import type { ContaminationScanResponse } from "@/lib/api/types";

export function useContaminationScan(agent_id: string | null) {
  return useSWR<ContaminationScanResponse>(
    agent_id ? `/grounding/scan/${agent_id}` : null,
    () => scanContamination(agent_id!),
    { revalidateOnFocus: false, dedupingInterval: 5000 }
  );
}
