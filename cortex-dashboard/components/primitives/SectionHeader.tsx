"use client";

import type { ReactNode } from "react";

interface SectionHeaderProps {
  title: string;
  count?: number;
  children?: ReactNode;
}

export function SectionHeader({ title, count, children }: SectionHeaderProps) {
  return (
    <div className="flex items-center justify-between mb-5">
      <div className="flex items-center gap-2.5">
        <h2>{title}</h2>
        {count !== undefined && (
          <span className="text-[var(--text-ghost)] text-[14px] font-mono tabular-nums">
            ({count})
          </span>
        )}
      </div>
      {children && <div className="flex items-center gap-2">{children}</div>}
    </div>
  );
}
