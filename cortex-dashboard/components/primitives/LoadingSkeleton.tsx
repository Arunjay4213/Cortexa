"use client";

export function LoadingSkeleton({
  rows = 3,
  className = "",
}: {
  rows?: number;
  className?: string;
}) {
  return (
    <div className={`space-y-2.5 ${className}`}>
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 bg-[var(--bg-surface-2)] rounded-md shimmer"
          style={{ width: `${100 - i * 15}%` }}
        />
      ))}
    </div>
  );
}

export function CardSkeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`card space-y-3 ${className}`}
    >
      <div className="h-3 bg-[var(--bg-surface-2)] rounded-md shimmer w-1/3" />
      <div className="h-7 bg-[var(--bg-surface-2)] rounded-md shimmer w-2/3" />
      <div className="h-3 bg-[var(--bg-surface-2)] rounded-md shimmer w-1/2" />
    </div>
  );
}

export function TableSkeleton({
  rows = 5,
  cols = 4,
}: {
  rows?: number;
  cols?: number;
}) {
  return (
    <div className="space-y-1.5">
      <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="h-3 bg-[var(--bg-surface-2)] rounded-md shimmer" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, r) => (
        <div
          key={r}
          className="grid gap-3"
          style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}
        >
          {Array.from({ length: cols }).map((_, c) => (
            <div
              key={c}
              className="h-4 bg-[var(--bg-surface-2)] rounded-md shimmer"
            />
          ))}
        </div>
      ))}
    </div>
  );
}
