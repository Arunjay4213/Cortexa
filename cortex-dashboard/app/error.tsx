"use client";

import { AlertCircle } from "lucide-react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="min-h-screen bg-[var(--bg-base)] flex items-center justify-center">
      <div className="card p-8 max-w-md text-center">
        <AlertCircle size={32} className="text-[var(--status-error)] mx-auto mb-4" />
        <div className="text-[var(--status-error)] text-xs font-medium mb-2 uppercase tracking-wider">
          System Error
        </div>
        <div className="text-[var(--text-secondary)] text-sm mb-1">{error.message}</div>
        {error.digest && (
          <div className="text-[var(--text-ghost)] text-[12px] font-mono mb-4">
            Digest: {error.digest}
          </div>
        )}
        <button
          onClick={reset}
          className="btn btn--secondary mt-4"
        >
          Retry
        </button>
      </div>
    </div>
  );
}
