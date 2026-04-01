"use client";

import { useEffect, useState } from "react";

export function StatusBar() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed((e) => e + 1);
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  // Reset every 10s to simulate live sync
  const syncAgo = elapsed % 10;

  return (
    <div className="h-7 shrink-0 bg-zinc-900 border-t border-zinc-800 flex items-center justify-between px-4 text-xs font-mono select-none">
      {/* Left: connection status */}
      <div className="flex items-center gap-2 text-zinc-500">
        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
        <span>Connected to agent-cs-prod</span>
      </div>

      {/* Center: QPS */}
      <div className="text-zinc-500">
        <span className="text-zinc-400 tabular-nums">42.3</span>
        <span className="ml-1">queries/sec</span>
      </div>

      {/* Right: last sync + docs */}
      <div className="flex items-center gap-3 text-zinc-500">
        <span>
          Last sync: <span className="text-zinc-400 tabular-nums">{syncAgo}s ago</span>
        </span>
        <span className="text-zinc-700">|</span>
        <a
          href="https://docs.cortexa.dev"
          target="_blank"
          rel="noopener noreferrer"
          className="text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          Docs
        </a>
      </div>
    </div>
  );
}
