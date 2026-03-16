"use client";

import type { ReactNode } from "react";

interface GrafanaPanelProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  /** Extra content rendered inline with the title (right side) */
  headerRight?: ReactNode;
  /** Remove default body padding */
  noPadding?: boolean;
}

export function GrafanaPanel({
  title,
  description,
  children,
  className = "",
  headerRight,
  noPadding = false,
}: GrafanaPanelProps) {
  return (
    <div
      className={`flex flex-col overflow-hidden ${className}`}
      style={{
        background: "var(--panel-bg)",
        border: "1px solid var(--panel-border)",
        borderRadius: "var(--panel-radius)",
      }}
    >
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-4 shrink-0"
        style={{ height: 36, borderBottom: "1px solid var(--panel-border)" }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="text-[13px] font-medium truncate"
            style={{ color: "var(--grafana-text-primary)" }}
          >
            {title}
          </span>
          {description && (
            <span
              className="text-[11px] truncate hidden sm:inline"
              style={{ color: "var(--grafana-text-muted)" }}
            >
              {description}
            </span>
          )}
        </div>
        {headerRight && <div className="shrink-0 ml-2">{headerRight}</div>}
      </div>

      {/* Panel body */}
      <div className={`flex-1 min-h-0 ${noPadding ? "" : "p-4"}`}>
        {children}
      </div>
    </div>
  );
}
