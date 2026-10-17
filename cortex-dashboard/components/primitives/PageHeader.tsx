"use client";

import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  badge?: ReactNode;
  children?: ReactNode;
}

export function PageHeader({ title, subtitle, badge, children }: PageHeaderProps) {
  return (
    <div className="flex items-start justify-between mb-10">
      <div>
        <div className="flex items-center gap-3">
          <h1>{title}</h1>
          {badge}
        </div>
        {subtitle && (
          <p className="mt-2 text-[var(--text-tertiary)] text-[15px]">{subtitle}</p>
        )}
      </div>
      {children && <div className="flex items-center gap-3 shrink-0">{children}</div>}
    </div>
  );
}
