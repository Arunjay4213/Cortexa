"use client";

import { useState, useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { Shield, ShieldAlert, ShieldCheck, Search } from "lucide-react";
import { useAgents } from "@/lib/hooks";
import {
  scanContamination,
  gateCheckMemory,
  quarantineSimulation,
} from "@/lib/api/grounding";
import type {
  ContaminationScanResponse,
  GateCheckResponse,
  QuarantineSimulationResponse,
} from "@/lib/api/types";
import { PageTransition } from "@/components/primitives/PageTransition";
import { PageHeader } from "@/components/primitives/PageHeader";
import { SectionHeader } from "@/components/primitives/SectionHeader";
import { MetricCard } from "@/components/primitives/MetricCard";
import { EmptyState } from "@/components/primitives/EmptyState";
import { ErrorFallback } from "@/components/primitives/ErrorFallback";
import { CardSkeleton } from "@/components/primitives/LoadingSkeleton";
import { EntityLink } from "@/components/primitives/EntityLink";

// ── Constants ────────────────────────────────────────────────────────

const PIE_COLORS = ["#6366F1", "#34D399", "#FBBF24", "#F87171"];

const RISK_BADGE: Record<string, string> = {
  high: "badge badge--error",
  medium: "badge badge--warning",
  low: "badge badge--success",
  trusted: "badge badge--success",
  uncertain: "badge badge--warning",
  suspect: "badge badge--warning",
  contaminated: "badge badge--error",
};

function riskBadgeClass(level: string): string {
  return RISK_BADGE[level.toLowerCase()] ?? "badge badge--warning";
}

// ── Page ─────────────────────────────────────────────────────────────

export default function GroundingPage() {
  const { data: agents } = useAgents();

  // Agent selection
  const [selectedAgent, setSelectedAgent] = useState("");

  // Scan state
  const [isScanning, setIsScanning] = useState(false);
  const [scanResult, setScanResult] = useState<ContaminationScanResponse | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  // Gate check state
  const [gateContent, setGateContent] = useState("");
  const [isGateChecking, setIsGateChecking] = useState(false);
  const [gateResult, setGateResult] = useState<GateCheckResponse | null>(null);
  const [gateError, setGateError] = useState<string | null>(null);

  // Quarantine simulation state
  const [quarantineMemoryId, setQuarantineMemoryId] = useState("");
  const [isQuarantining, setIsQuarantining] = useState(false);
  const [quarantineResult, setQuarantineResult] = useState<QuarantineSimulationResponse | null>(null);
  const [quarantineError, setQuarantineError] = useState<string | null>(null);

  // ── Derived data ───────────────────────────────────────────────────

  const flags = scanResult?.flags ?? [];

  const riskCounts = useMemo(() => {
    if (!scanResult) return null;
    let high = 0;
    let medium = 0;
    let low = 0;
    for (const f of flags) {
      const level = f.risk_level.toLowerCase();
      if (level === "contaminated" || level === "high") high++;
      else if (level === "suspect" || level === "uncertain" || level === "medium") medium++;
      else low++;
    }
    return { high, medium, low, total: flags.length };
  }, [scanResult, flags]);

  const pieData = useMemo(() => {
    if (!riskCounts) return [];
    return [
      { name: "High Risk", value: riskCounts.high },
      { name: "Low Risk", value: riskCounts.low },
      { name: "Medium Risk", value: riskCounts.medium },
      { name: "Trusted", value: riskCounts.total - riskCounts.high - riskCounts.medium - riskCounts.low },
    ].filter((d) => d.value > 0);
  }, [riskCounts]);

  // ── Handlers ───────────────────────────────────────────────────────

  async function handleScan() {
    if (!selectedAgent) return;
    setIsScanning(true);
    setScanError(null);
    setScanResult(null);
    try {
      const result = await scanContamination(selectedAgent);
      setScanResult(result);
    } catch (err: unknown) {
      setScanError(err instanceof Error ? err.message : "Scan failed");
    } finally {
      setIsScanning(false);
    }
  }

  async function handleGateCheck() {
    if (!selectedAgent || !gateContent.trim()) return;
    setIsGateChecking(true);
    setGateResult(null);
    setGateError(null);
    try {
      const result = await gateCheckMemory(selectedAgent, gateContent.trim());
      setGateResult(result);
    } catch (err: unknown) {
      setGateError(err instanceof Error ? err.message : "Gate check failed");
    } finally {
      setIsGateChecking(false);
    }
  }

  async function handleQuarantineSimulation() {
    if (!selectedAgent || !quarantineMemoryId.trim()) return;
    setIsQuarantining(true);
    setQuarantineResult(null);
    setQuarantineError(null);
    try {
      const result = await quarantineSimulation(selectedAgent, [quarantineMemoryId.trim()]);
      setQuarantineResult(result);
    } catch (err: unknown) {
      setQuarantineError(err instanceof Error ? err.message : "Quarantine simulation failed");
    } finally {
      setIsQuarantining(false);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <PageTransition>
      <div className="space-y-6">
        <PageHeader
          title="Grounding"
          subtitle="Contamination scanning, gate checks, and quarantine simulation"
        >
          <select
            value={selectedAgent}
            onChange={(e) => {
              setSelectedAgent(e.target.value);
              setScanResult(null);
              setScanError(null);
              setGateResult(null);
              setGateError(null);
              setQuarantineResult(null);
              setQuarantineError(null);
            }}
            className="input w-52"
          >
            <option value="">Select agent...</option>
            {(agents ?? []).map((a) => (
              <option key={a.agent_id} value={a.agent_id}>
                {a.agent_id}
              </option>
            ))}
          </select>
          <button
            onClick={handleScan}
            disabled={!selectedAgent || isScanning}
            className="btn btn--primary"
          >
            {isScanning ? "Scanning..." : "Run Scan"}
          </button>
        </PageHeader>

        {/* Scan Error */}
        {scanError && (
          <ErrorFallback error={scanError} onRetry={handleScan} />
        )}

        {/* Loading skeleton */}
        {isScanning && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
        )}

        {/* Scan Results */}
        {scanResult && riskCounts && (
          <>
            {/* Summary Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <MetricCard
                label="Total Flags"
                value={riskCounts.total}
              />
              <MetricCard
                label="High Risk"
                value={riskCounts.high}
              />
              <MetricCard
                label="Medium Risk"
                value={riskCounts.medium}
              />
              <MetricCard
                label="Low Risk"
                value={riskCounts.low}
              />
            </div>

            {/* Risk Distribution Pie Chart */}
            {pieData.length > 0 && (
              <div className="card">
                <SectionHeader title="Risk Distribution" count={flags.length} />
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={90}
                        paddingAngle={2}
                        dataKey="value"
                        nameKey="name"
                      >
                        {pieData.map((_, i) => (
                          <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          background: "var(--bg-surface-2)",
                          border: "1px solid var(--border-default)",
                          borderRadius: "6px",
                          fontSize: "12px",
                          color: "var(--text-secondary)",
                        }}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Flags Table */}
            <div className="card p-0 overflow-hidden">
              <div className="px-5 pt-5 pb-3">
                <SectionHeader title="Flagged Memories" count={flags.length} />
              </div>
              <div className="overflow-x-auto">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Memory ID</th>
                      <th>Risk Level</th>
                      <th>Flag Type</th>
                      <th>Explanation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {flags.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="text-center py-8 text-[var(--text-ghost)]">
                          No flags found
                        </td>
                      </tr>
                    ) : (
                      flags.map((flag) => (
                        <tr key={flag.memory_id}>
                          <td>
                            <EntityLink type="memory" id={flag.memory_id} truncate={12} />
                          </td>
                          <td>
                            <span className={riskBadgeClass(flag.risk_level)}>
                              {flag.risk_level}
                            </span>
                          </td>
                          <td className="font-mono text-[var(--text-secondary)]">
                            {flag.recommended_action}
                          </td>
                          <td className="text-[var(--text-tertiary)] max-w-xs truncate">
                            {flag.reasons.length > 0 ? flag.reasons.join("; ") : "--"}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* Empty state when no scan has been run */}
        {!scanResult && !isScanning && !scanError && (
          <EmptyState
            icon={<Search size={40} strokeWidth={1} />}
            title="No scan results"
            description="Select an agent and run a contamination scan to check memory grounding, provenance, and risk levels."
          />
        )}

        {/* ── Tools Section ─────────────────────────────────────────── */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Gate Check Tool */}
          <div className="card">
            <SectionHeader title="Gate Check" />
            <p className="text-sm text-[var(--text-tertiary)] mb-4">
              Check whether a candidate memory should be stored based on grounding analysis.
            </p>
            <div className="space-y-3">
              <textarea
                value={gateContent}
                onChange={(e) => setGateContent(e.target.value)}
                placeholder="Paste memory content to check..."
                className="input w-full h-24 resize-none"
              />
              <button
                onClick={handleGateCheck}
                disabled={!selectedAgent || !gateContent.trim() || isGateChecking}
                className="btn btn--primary w-full"
              >
                {isGateChecking ? "Checking..." : "Check"}
              </button>
            </div>

            {gateError && (
              <div className="mt-3">
                <ErrorFallback error={gateError} onRetry={handleGateCheck} />
              </div>
            )}

            {gateResult && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {gateResult.should_store ? (
                      <ShieldCheck size={18} className="text-[var(--status-success)]" />
                    ) : (
                      <ShieldAlert size={18} className="text-[var(--status-error)]" />
                    )}
                    <span className={`text-sm font-semibold ${
                      gateResult.should_store
                        ? "text-[var(--status-success)]"
                        : "text-[var(--status-error)]"
                    }`}>
                      {gateResult.should_store ? "PASS - Should Store" : "FAIL - Reject"}
                    </span>
                  </div>
                  <span className={riskBadgeClass(gateResult.risk_level)}>
                    {gateResult.risk_level}
                  </span>
                </div>

                <div className="text-sm text-[var(--text-tertiary)]">
                  Grounding Score:{" "}
                  <span className="font-mono text-[var(--text-secondary)]">
                    {(gateResult.grounding_score * 100).toFixed(1)}%
                  </span>
                </div>

                {gateResult.reasons.length > 0 && (
                  <div className="space-y-1">
                    {gateResult.reasons.map((r, i) => (
                      <div key={i} className="text-xs text-[var(--text-tertiary)]">
                        &bull; {r}
                      </div>
                    ))}
                  </div>
                )}

                {gateResult.contradicts_existing.length > 0 && (
                  <div className="text-xs text-[var(--status-error)]">
                    Contradicts:{" "}
                    <span className="font-mono">
                      {gateResult.contradicts_existing.map((id) => id.slice(0, 8)).join(", ")}
                    </span>
                  </div>
                )}

                {gateResult.redundant_with.length > 0 && (
                  <div className="text-xs text-[var(--status-warning)]">
                    Redundant with:{" "}
                    <span className="font-mono">
                      {gateResult.redundant_with.map((id) => id.slice(0, 8)).join(", ")}
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Quarantine Simulation Tool */}
          <div className="card">
            <SectionHeader title="Quarantine Simulation" />
            <p className="text-sm text-[var(--text-tertiary)] mb-4">
              Simulate the impact of quarantining a memory on system health.
            </p>
            <div className="space-y-3">
              <input
                type="text"
                value={quarantineMemoryId}
                onChange={(e) => setQuarantineMemoryId(e.target.value)}
                placeholder="Enter memory ID..."
                className="input w-full font-mono"
              />
              <button
                onClick={handleQuarantineSimulation}
                disabled={!selectedAgent || !quarantineMemoryId.trim() || isQuarantining}
                className="btn btn--primary w-full"
              >
                {isQuarantining ? "Simulating..." : "Simulate"}
              </button>
            </div>

            {quarantineError && (
              <div className="mt-3">
                <ErrorFallback error={quarantineError} onRetry={handleQuarantineSimulation} />
              </div>
            )}

            {quarantineResult && (
              <div className="mt-4 space-y-3">
                <div className="flex items-center gap-2 mb-2">
                  <Shield size={18} className={
                    quarantineResult.health_improved
                      ? "text-[var(--status-success)]"
                      : "text-[var(--status-warning)]"
                  } />
                  <span className={`text-sm font-semibold ${
                    quarantineResult.health_improved
                      ? "text-[var(--status-success)]"
                      : "text-[var(--status-warning)]"
                  }`}>
                    {quarantineResult.health_improved ? "Health Improved" : "Health Not Improved"}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-[var(--bg-surface-2)] rounded-lg p-3">
                    <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
                      CHI Before
                    </div>
                    <div className="text-sm font-semibold text-[var(--text-primary)] font-mono">
                      {quarantineResult.chi_before?.toFixed(4) ?? "--"}
                    </div>
                  </div>
                  <div className="bg-[var(--bg-surface-2)] rounded-lg p-3">
                    <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
                      CHI After
                    </div>
                    <div className={`text-sm font-semibold font-mono ${
                      quarantineResult.health_improved
                        ? "text-[var(--status-success)]"
                        : "text-[var(--status-error)]"
                    }`}>
                      {quarantineResult.chi_after?.toFixed(4) ?? "--"}
                    </div>
                  </div>
                  <div className="bg-[var(--bg-surface-2)] rounded-lg p-3">
                    <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
                      Coverage Gap Change
                    </div>
                    <div className={`text-sm font-semibold font-mono ${
                      quarantineResult.coverage_gap_change <= 0
                        ? "text-[var(--status-success)]"
                        : "text-[var(--status-error)]"
                    }`}>
                      {quarantineResult.coverage_gap_change > 0 ? "+" : ""}
                      {quarantineResult.coverage_gap_change}
                    </div>
                  </div>
                  <div className="bg-[var(--bg-surface-2)] rounded-lg p-3">
                    <div className="text-xs text-[var(--text-tertiary)] uppercase tracking-wider mb-1">
                      Transactions Affected
                    </div>
                    <div className="text-sm font-semibold text-[var(--text-primary)] font-mono">
                      {quarantineResult.transactions_affected}
                    </div>
                  </div>
                </div>

                {quarantineResult.recommendation && (
                  <div className="bg-[var(--bg-surface-2)] rounded-lg p-3 text-sm text-[var(--text-tertiary)]">
                    <span className="text-xs text-[var(--text-ghost)] uppercase tracking-wider">
                      Recommendation:{" "}
                    </span>
                    {quarantineResult.recommendation}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </PageTransition>
  );
}
