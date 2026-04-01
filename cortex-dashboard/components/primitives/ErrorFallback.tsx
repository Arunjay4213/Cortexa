"use client";

import { AlertCircle } from "lucide-react";

export function ErrorFallback({
  error,
  onRetry,
}: {
  error: Error | string;
  onRetry?: () => void;
}) {
  const message = typeof error === "string" ? error : error.message;

  return (
    <div className="card flex items-start gap-3 p-5">
      <AlertCircle size={18} className="text-[var(--status-error)] shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <div className="text-[var(--status-error)] text-xs font-medium uppercase tracking-wider mb-1">
          Error
        </div>
        <div className="text-[var(--text-secondary)] text-sm">{message}</div>
        {onRetry && (
          <button
            onClick={onRetry}
            className="btn btn--secondary mt-3 text-xs"
          >
            Retry
          </button>
        )}
      </div>
    </div>
  );
}
