"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import { CommandPalette } from "@/components/CommandPalette";
import { useMemories, useTransactions, useAgents } from "@/lib/hooks";
import {
  LayoutDashboard,
  Target,
  Database,
  HeartPulse,
  Users,
  Cpu,
  Shield,
  FlaskConical,
  GitBranch,
  Search,
  Wifi,
  WifiOff,
} from "lucide-react";

const NAV_LINKS = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/attribution", label: "Attribution", icon: Target },
  { href: "/memories", label: "Memories", icon: Database },
  { href: "/health", label: "Health", icon: HeartPulse },
  { href: "/fleet", label: "Fleet", icon: Users },
  { href: "/engine", label: "Engine", icon: Cpu },
  { href: "/grounding", label: "Grounding", icon: Shield },
  { href: "/staging", label: "Staging", icon: FlaskConical },
  { href: "/snapshots", label: "Snapshots", icon: GitBranch },
];

export function Navigation() {
  const pathname = usePathname();
  const { connected } = useWebSocket();
  const [clock, setClock] = useState("");

  // Fetch entity data for CommandPalette
  const { data: memoriesData } = useMemories({ limit: 100 });
  const { data: transactionsData } = useTransactions({ limit: 50 });
  const { data: agentsData } = useAgents();

  useEffect(() => {
    const tick = () => {
      const now = new Date();
      setClock(
        now.toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    };
    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, []);

  const cmdMemories = (memoriesData?.items ?? []).map((m: any) => ({
    id: m.id,
    content: m.content ?? "",
  }));
  const cmdTransactions = (transactionsData?.items ?? []).map((t: any) => ({
    id: t.id,
    query_text: t.query_text ?? "",
  }));
  const cmdAgents = (agentsData ?? []).map((a: any) => ({
    agent_id: a.agent_id,
  }));

  const openCommandPalette = () => {
    window.dispatchEvent(
      new KeyboardEvent("keydown", {
        key: "k",
        metaKey: true,
        bubbles: true,
      })
    );
  };

  return (
    <>
      <CommandPalette
        memories={cmdMemories}
        agents={cmdAgents}
        transactions={cmdTransactions}
      />

      {/* Sidebar */}
      <aside className="fixed top-0 left-0 h-screen w-[var(--sidebar-width)] bg-[var(--bg-surface-1)] border-r border-[var(--border-default)] z-40 flex flex-col">
        {/* Logo */}
        <div className="px-5 h-16 flex items-center gap-2.5 shrink-0">
          <div className="w-7 h-7 rounded-lg bg-[var(--accent)] flex items-center justify-center">
            <span className="text-white text-xs font-bold">C</span>
          </div>
          <span className="text-[var(--text-primary)] text-[15px] font-semibold tracking-tight">
            CortexOS
          </span>
        </div>

        {/* Nav Links */}
        <nav className="flex-1 px-3 py-3 overflow-y-auto">
          <div className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => {
              const isActive =
                link.href === "/"
                  ? pathname === "/"
                  : pathname.startsWith(link.href);
              const Icon = link.icon;

              return (
                <Link key={link.href} href={link.href}>
                  <span
                    className={`relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13px] font-medium transition-all duration-200 ${
                      isActive
                        ? "bg-[var(--accent-muted)] text-[var(--accent)]"
                        : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface-2)] active:scale-[0.98]"
                    }`}
                  >
                    {isActive && (
                      <span className="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-4 bg-[var(--accent)] rounded-r-full" />
                    )}
                    <Icon size={16} strokeWidth={1.5} />
                    {link.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Bottom Section */}
        <div className="px-3 pb-4 shrink-0 flex flex-col gap-2">
          {/* Command Palette Trigger */}
          <button
            onClick={openCommandPalette}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-surface-2)] transition-colors"
          >
            <Search size={14} strokeWidth={1.5} />
            <span className="text-[12px]">Search</span>
            <kbd className="ml-auto text-[11px] text-[var(--text-ghost)] bg-[var(--bg-surface-2)] border border-[var(--border-default)] rounded px-1.5 py-0.5 font-mono">
              &#8984;K
            </kbd>
          </button>

          {/* Divider */}
          <div className="border-t border-[var(--border-default)]" />

          {/* Connection Status + Clock */}
          <div className="flex items-center justify-between px-3 py-1.5">
            <div className="flex items-center gap-2">
              {connected ? (
                <span className="live-dot" />
              ) : (
                <WifiOff size={14} className="text-[var(--status-error)]" />
              )}
              <span className="text-[12px] text-[var(--text-tertiary)]">
                {connected ? "Live" : "Offline"}
              </span>
            </div>
            <span className="text-[12px] text-[var(--text-ghost)] font-mono tabular-nums">
              {clock}
            </span>
          </div>
        </div>
      </aside>
    </>
  );
}
