import useSWR from "swr";
import { getSession } from "@/lib/api/counterfactual";
import type { CounterfactualResult } from "@/lib/api/types";

export function useCounterfactualSession(session_id: string | null) {
  return useSWR<CounterfactualResult>(
    session_id ? `/counterfactual/${session_id}` : null,
    () => getSession(session_id!),
    { revalidateOnFocus: false, dedupingInterval: 2000 }
  );
}
