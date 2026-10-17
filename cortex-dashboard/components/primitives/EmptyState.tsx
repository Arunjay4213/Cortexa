"use client";

import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  children?: ReactNode;
}

export function EmptyState({ icon, title, description, children }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="text-[var(--text-ghost)] mb-4">
        {icon ?? <Inbox size={40} strokeWidth={1} />}
      </div>
      <h3 className="text-[var(--text-secondary)] mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-[var(--text-tertiary)] max-w-sm">{description}</p>
      )}
      {children && <div className="mt-4">{children}</div>}
    </div>
  );
}
