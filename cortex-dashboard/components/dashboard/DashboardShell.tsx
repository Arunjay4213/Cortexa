"use client";

import { useState, useEffect, useCallback } from "react";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandPalette } from "./CommandPalette";
import { MemoryDetailPanel } from "@/components/shared/MemoryDetailPanel";

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(null);

  // Global Cmd+K / Ctrl+K listener
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setCmdPaletteOpen((prev) => !prev);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, []);

  const handleSelectMemory = useCallback((memoryId: string) => {
    setCmdPaletteOpen(false);
    setSelectedMemoryId(memoryId);
  }, []);

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Fixed narrow sidebar — 56px */}
      <Sidebar />

      {/* Main area: topbar + scrollable content */}
      <div className="flex-1 flex flex-col h-screen" style={{ marginLeft: 56 }}>
        <TopBar onOpenSearch={() => setCmdPaletteOpen(true)} />

        <main
          className="flex-1 overflow-y-auto"
          style={{ background: "var(--dashboard-bg)" }}
        >
          <div style={{ padding: "var(--panel-gap)" }}>
            {children}
          </div>
        </main>
      </div>

      {/* Global overlays */}
      <CommandPalette
        open={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onSelectMemory={handleSelectMemory}
      />
      <MemoryDetailPanel
        memoryId={selectedMemoryId}
        onClose={() => setSelectedMemoryId(null)}
      />
    </div>
  );
}
