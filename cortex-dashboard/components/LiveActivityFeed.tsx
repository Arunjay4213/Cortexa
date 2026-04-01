"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useWebSocket } from "@/lib/providers/WebSocketProvider";
import {
  Database,
  ArrowRight,
  Star,
  RefreshCw,
  Settings,
  AlertTriangle,
  Activity,
  ChevronRight,
  ChevronDown,
} from "lucide-react";

interface ActivityEvent {
  id: string;
  type: string;
  description: string;
  timestamp: number;
  link?: string;
}

const EVENT_ICONS: Record<string, React.ReactNode> = {
  memory_update: <Database size={12} />,
  transaction_created: <ArrowRight size={12} />,
  attribution_scored: <Star size={12} />,
  lifecycle_executed: <RefreshCw size={12} />,
  agent_updated: <Settings size={12} />,
  transaction: <ArrowRight size={12} />,
  contradiction: <AlertTriangle size={12} />,
  score: <Star size={12} />,
};

const EVENT_COLORS: Record<string, string> = {
  memory_update: "text-[var(--accent)]",
  transaction_created: "text-[var(--status-success)]",
  attribution_scored: "text-[var(--status-warning)]",
  lifecycle_executed: "text-purple-400",
  agent_updated: "text-cyan-400",
  transaction: "text-[var(--status-success)]",
  contradiction: "text-[var(--status-error)]",
  score: "text-[var(--status-warning)]",
};

function formatEventDescription(type: string, data: Record<string, unknown>): string {
  const agentId = (data.agent_id as string) ?? "";
  switch (type) {
    case "memory_update":
      return `Memory updated for ${agentId}`;
    case "transaction_created":
      return `New transaction by ${agentId}`;
    case "attribution_scored":
      return `Attribution scored for ${agentId}`;
    case "lifecycle_executed":
      return `Lifecycle optimization on ${agentId}`;
    case "agent_updated":
      return `Agent ${agentId} config updated`;
    case "transaction":
      return `Transaction processed`;
    case "contradiction":
      return `Contradiction detected`;
    case "score":
      return `Score computed`;
    default:
      return `Event: ${type}`;
  }
}

function formatEventLink(type: string, data: Record<string, unknown>): string | undefined {
  switch (type) {
    case "memory_update":
      return data.memory_id ? `/memories?selected=${data.memory_id}` : "/memories";
    case "transaction_created":
      return data.transaction_id ? `/attribution?selected=${data.transaction_id}` : "/attribution";
    case "agent_updated":
      return data.agent_id ? `/fleet?selected=${data.agent_id}` : "/fleet";
    default:
      return undefined;
  }
}

function relativeTime(ts: number): string {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 5) return "now";
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  return `${Math.floor(diff / 3600)}h`;
}

const MAX_EVENTS = 20;

export function LiveActivityFeed() {
  const { lastEvent, connected } = useWebSocket();
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [collapsed, setCollapsed] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!lastEvent) return;
    const evt: ActivityEvent = {
      id: `${lastEvent.sequence_id}-${Date.now()}`,
      type: lastEvent.type,
      description: formatEventDescription(lastEvent.type, lastEvent.data ?? lastEvent as any),
      timestamp: Date.now(),
      link: formatEventLink(lastEvent.type, lastEvent.data ?? lastEvent as any),
    };
    setEvents((prev) => [...prev.slice(-(MAX_EVENTS - 1)), evt]);
  }, [lastEvent]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [events]);

  return (
    <div className="border-t border-[var(--border-default)]">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full px-4 py-2 flex items-center justify-between text-[12px] text-[var(--text-tertiary)] hover:bg-[var(--bg-surface-1)] transition-colors"
      >
        <span className="flex items-center gap-2">
          <Activity size={12} />
          Live Activity
          {events.length > 0 && (
            <span className="text-[var(--accent)] font-mono tabular-nums">
              {events.length}
            </span>
          )}
        </span>
        {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
      </button>

      {!collapsed && (
        <div
          ref={scrollRef}
          className="max-h-[200px] overflow-y-auto border-t border-[var(--border-default)]"
        >
          {events.length === 0 ? (
            <div className="px-4 py-6 text-center text-[12px] text-[var(--text-ghost)]">
              {connected ? "Waiting for events..." : "WebSocket disconnected"}
            </div>
          ) : (
            events.map((evt) => (
              <div
                key={evt.id}
                className="flex items-center gap-2.5 px-4 py-1.5 text-[12px] border-b border-[var(--border-default)] hover:bg-[var(--bg-surface-1)] transition-colors"
              >
                <span className={`shrink-0 ${EVENT_COLORS[evt.type] ?? "text-[var(--text-tertiary)]"}`}>
                  {EVENT_ICONS[evt.type] ?? <Activity size={12} />}
                </span>
                <span className="flex-1 text-[var(--text-tertiary)] truncate">
                  {evt.description}
                </span>
                {evt.link && (
                  <Link
                    href={evt.link}
                    className="text-[var(--accent)] opacity-50 hover:opacity-100 shrink-0"
                  >
                    <ArrowRight size={12} />
                  </Link>
                )}
                <span className="text-[var(--text-ghost)] font-mono tabular-nums shrink-0 w-6 text-right text-[12px]">
                  {relativeTime(evt.timestamp)}
                </span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
