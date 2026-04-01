"use client";

import { usePathname } from "next/navigation";
import { Clock, ChevronDown, RefreshCw, Search, Star } from "lucide-react";

// ── Route → breadcrumb mapping ─────────────────────────────────────────

const ROUTE_LABELS: Record<string, string> = {
  "/": "Command Center",
  "/overview": "Command Center",
  "/attribution": "Attribution Explorer",
  "/health": "Health Monitor",
  "/lifecycle": "Budget Optimizer",
  "/compliance": "Compliance",
  "/memories": "Memories",
  "/fleet": "Fleet",
  "/engine": "Engine",
  "/grounding": "Grounding",
  "/staging": "Staging",
  "/snapshots": "Snapshots",
  "/alerts": "Alerts",
  "/settings": "Settings",
  "/docs": "API Documentation",
};

function getPageName(pathname: string): string {
  if (ROUTE_LABELS[pathname]) return ROUTE_LABELS[pathname];

  // Dynamic routes (e.g. /attribution/qt-001)
  const traceMatch = pathname.match(/^\/attribution\/(qt-\d+)$/);
  if (traceMatch) return `Trace ${traceMatch[1].toUpperCase()}`;

  // Fallback
  const segments = pathname.split("/").filter(Boolean);
  const parentPath = "/" + segments[0];
  return ROUTE_LABELS[parentPath] ?? segments[segments.length - 1] ?? "Dashboard";
}

// ── Component ──────────────────────────────────────────────────────────

interface TopBarProps {
  onOpenSearch: () => void;
}

export function TopBar({ onOpenSearch }: TopBarProps) {
  const pathname = usePathname();
  const pageName = getPageName(pathname);

  return (
    <header
      className="h-10 shrink-0 flex items-center justify-between px-4 z-30"
      style={{
        background: "var(--panel-bg)",
        borderBottom: "1px solid var(--panel-border)",
      }}
    >
      {/* Left: breadcrumb + favorite star */}
      <div className="flex items-center gap-2 min-w-0">
        <span
          className="text-[13px]"
          style={{ color: "var(--grafana-text-secondary)" }}
        >
          Cortexa
        </span>
        <span
          className="text-[13px]"
          style={{ color: "var(--grafana-text-disabled)" }}
        >
          /
        </span>
        <span
          className="text-[13px] font-medium truncate"
          style={{ color: "var(--grafana-text-primary)" }}
        >
          {pageName}
        </span>
        <button
          className="p-1 rounded-sm transition-colors duration-100"
          style={{ color: "var(--grafana-text-disabled)" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = "var(--grafana-yellow)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = "var(--grafana-text-disabled)";
          }}
          aria-label="Favorite this page"
        >
          <Star size={14} strokeWidth={1.5} />
        </button>
      </div>

      {/* Right: time range + refresh + search */}
      <div className="flex items-center gap-1">
        {/* Time range picker (decorative) */}
        <button
          className="flex items-center gap-1.5 px-2.5 h-7 rounded-sm text-[12px] font-mono transition-colors duration-100"
          style={{
            border: "1px solid var(--panel-border)",
            color: "var(--grafana-text-primary)",
            background: "transparent",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--border-hover)";
            e.currentTarget.style.background = "var(--panel-bg-hover)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--panel-border)";
            e.currentTarget.style.background = "transparent";
          }}
          aria-label="Select time range"
        >
          <Clock size={13} strokeWidth={1.5} style={{ color: "var(--grafana-text-muted)" }} />
          <span>Last 24 hours</span>
          <ChevronDown size={12} strokeWidth={1.5} style={{ color: "var(--grafana-text-muted)" }} />
        </button>

        {/* Refresh button */}
        <button
          className="flex items-center justify-center w-7 h-7 rounded-sm transition-colors duration-100"
          style={{
            color: "var(--grafana-text-muted)",
            background: "transparent",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--panel-bg-hover)";
            e.currentTarget.style.color = "var(--grafana-text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--grafana-text-muted)";
          }}
          aria-label="Refresh dashboard"
        >
          <RefreshCw size={14} strokeWidth={1.5} />
        </button>

        {/* Separator */}
        <div
          className="w-px h-4 mx-1"
          style={{ background: "var(--panel-border)" }}
        />

        {/* Search button → opens command palette */}
        <button
          onClick={onOpenSearch}
          className="flex items-center justify-center w-7 h-7 rounded-sm transition-colors duration-100"
          style={{
            color: "var(--grafana-text-muted)",
            background: "transparent",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--panel-bg-hover)";
            e.currentTarget.style.color = "var(--grafana-text-primary)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.color = "var(--grafana-text-muted)";
          }}
          aria-label="Search (Cmd+K)"
        >
          <Search size={14} strokeWidth={1.5} />
        </button>
      </div>
    </header>
  );
}
