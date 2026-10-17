"use client";

import React from "react";
import { SWRConfig } from "swr";

export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        refreshInterval: 30000,
        revalidateOnFocus: true,
        dedupingInterval: 2000,
        errorRetryCount: 3,
        onErrorRetry: (error, _key, _config, revalidate, { retryCount }) => {
          if (retryCount >= 3) return;
          const delay = Math.min(1000 * Math.pow(2, retryCount), 10000);
          setTimeout(() => revalidate({ retryCount }), delay);
        },
      }}
    >
      {children}
    </SWRConfig>
  );
}
