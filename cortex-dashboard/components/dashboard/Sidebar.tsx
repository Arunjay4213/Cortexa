"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";
import * as Tooltip from "@radix-ui/react-tooltip";
import {
  LayoutDashboard,
  Search,
  Activity,
  Layers,
  Shield,
  Bell,
  Settings,
  BookOpen,
  LogOut,
} from "lucide-react";
import { mockHealthAlerts } from "@/lib/mock-data";
import { useAuth } from "@/lib/providers/AuthProvider";

// ── Navigation items ─────────────────────────────────────────────────

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
  badge?: number;
};

const TOP_NAV: NavItem[] = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/attribution", label: "Attribution", icon: Search },
  { href: "/health", label: "Health", icon: Activity },
  { href: "/lifecycle", label: "Lifecycle", icon: Layers },
  { href: "/compliance", label: "Compliance", icon: Shield },
];

const unresolvedAlerts = mockHealthAlerts.filter((a) => !a.resolved).length;

const BOTTOM_NAV: NavItem[] = [
  { href: "/docs", label: "Docs", icon: BookOpen },
  { href: "/alerts", label: "Alerts", icon: Bell, badge: unresolvedAlerts > 0 ? unresolvedAlerts : undefined },
  { href: "/settings", label: "Settings", icon: Settings },
];

// ── Component ────────────────────────────────────────────────────────

export function Sidebar() {
  const pathname = usePathname();
  const { logout } = useAuth();

  const isActive = (href: string) => {
    if (href === "/overview") return pathname === "/overview" || pathname === "/";
    return pathname.startsWith(href);
  };

  const renderItem = (item: NavItem) => {
    const active = isActive(item.href);
    const Icon = item.icon;

    return (
      <Tooltip.Root key={item.href} delayDuration={0}>
        <Tooltip.Trigger asChild>
          <Link
            href={item.href}
            className="relative flex items-center justify-center w-10 h-10 mx-auto"
            aria-label={item.label}
          >
            {/* Active left accent bar */}
            {active && (
              <span
                className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-sm"
                style={{ background: "var(--grafana-green)" }}
              />
            )}

            {/* Icon container */}
            <span
              className="flex items-center justify-center w-10 h-10 rounded-sm transition-colors duration-100"
              style={{
                background: active ? "rgba(115, 191, 105, 0.1)" : "transparent",
                color: active ? "var(--grafana-green)" : "var(--grafana-text-muted)",
              }}
              onMouseEnter={(e) => {
                if (!active) {
                  e.currentTarget.style.background = "var(--panel-bg-hover)";
                  e.currentTarget.style.color = "var(--grafana-text-primary)";
                }
              }}
              onMouseLeave={(e) => {
                if (!active) {
                  e.currentTarget.style.background = "transparent";
                  e.currentTarget.style.color = "var(--grafana-text-muted)";
                }
              }}
            >
              <Icon size={20} strokeWidth={1.5} />
            </span>

            {/* Alert badge (red dot) */}
            {item.badge !== undefined && item.badge > 0 && (
              <span
                className="absolute top-1 right-1 w-2 h-2 rounded-full"
                style={{ background: "var(--grafana-red)" }}
              />
            )}
          </Link>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            side="right"
            sideOffset={8}
            className="z-50 rounded-sm px-3 py-1.5 text-xs animate-fade-in"
            style={{
              background: "var(--panel-bg-hover)",
              color: "var(--grafana-text-primary)",
              border: "1px solid var(--panel-border)",
            }}
          >
            {item.label}
            {item.badge !== undefined && item.badge > 0 && (
              <span
                className="ml-2 text-[10px] font-mono"
                style={{ color: "var(--grafana-red)" }}
              >
                {item.badge}
              </span>
            )}
            <Tooltip.Arrow style={{ fill: "var(--panel-bg-hover)" }} />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    );
  };

  return (
    <Tooltip.Provider>
      <aside
        className="fixed top-0 left-0 h-screen w-14 flex flex-col z-40 select-none"
        style={{
          background: "#0b0c0e",
          borderRight: "1px solid var(--panel-border)",
        }}
      >
        {/* Logo */}
        <div className="h-10 flex items-center justify-center shrink-0"
          style={{ borderBottom: "1px solid var(--panel-border)" }}
        >
          <div
            className="w-7 h-7 rounded-sm flex items-center justify-center"
            style={{ background: "var(--grafana-green)" }}
          >
            <span className="text-white text-[11px] font-bold tracking-tight">C</span>
          </div>
        </div>

        {/* Top nav items */}
        <nav className="flex-1 flex flex-col items-center pt-2 gap-0.5">
          {TOP_NAV.map(renderItem)}
        </nav>

        {/* Divider + bottom nav */}
        <div className="flex flex-col items-center pb-2 gap-0.5">
          <div
            className="w-6 mb-1"
            style={{ borderTop: "1px solid var(--panel-border)" }}
          />
          {BOTTOM_NAV.map(renderItem)}

          {/* Logout */}
          <Tooltip.Root delayDuration={0}>
            <Tooltip.Trigger asChild>
              <button
                onClick={logout}
                className="relative flex items-center justify-center w-10 h-10 mx-auto"
                aria-label="Logout"
              >
                <span
                  className="flex items-center justify-center w-10 h-10 rounded-sm transition-colors duration-100"
                  style={{
                    color: "var(--grafana-text-muted)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "var(--panel-bg-hover)";
                    e.currentTarget.style.color = "var(--grafana-red)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "transparent";
                    e.currentTarget.style.color = "var(--grafana-text-muted)";
                  }}
                >
                  <LogOut size={20} strokeWidth={1.5} />
                </span>
              </button>
            </Tooltip.Trigger>
            <Tooltip.Portal>
              <Tooltip.Content
                side="right"
                sideOffset={8}
                className="z-50 rounded-sm px-3 py-1.5 text-xs animate-fade-in"
                style={{
                  background: "var(--panel-bg-hover)",
                  color: "var(--grafana-text-primary)",
                  border: "1px solid var(--panel-border)",
                }}
              >
                Logout
                <Tooltip.Arrow style={{ fill: "var(--panel-bg-hover)" }} />
              </Tooltip.Content>
            </Tooltip.Portal>
          </Tooltip.Root>
        </div>
      </aside>
    </Tooltip.Provider>
  );
}
