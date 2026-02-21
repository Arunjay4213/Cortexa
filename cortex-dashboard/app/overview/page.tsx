"use client";

import { KPIStrip } from "@/components/dashboard/KPIStrip";
import { LiveFeed } from "@/components/dashboard/LiveFeed";
import { HealthSummary } from "@/components/dashboard/HealthSummary";
import { MemoryPLTable } from "@/components/dashboard/MemoryPLTable";
import { ComplianceStatus } from "@/components/dashboard/ComplianceStatus";

export default function OverviewPage() {
  return (
    <div className="space-y-6">
      {/* Row 1: KPI Strip — full width */}
      <KPIStrip />

      {/* Row 2: Live Feed (60%) + Health Summary (40%) */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3">
          <LiveFeed />
        </div>
        <div className="lg:col-span-2">
          <HealthSummary />
        </div>
      </div>

      {/* Row 3: Memory P&L Table (50%) + Compliance Status (50%) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MemoryPLTable />
        <ComplianceStatus />
      </div>
    </div>
  );
}
