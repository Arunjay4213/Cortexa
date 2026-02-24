/**
 * Mock data for the Cortexa dashboard.
 *
 * The data tells several interleaved stories:
 *
 * 1. **Subscription hallucination** — Memory #47 (stale, says "renews monthly")
 *    dominates attribution for a subscription-status query while Memory #198
 *    (current, says "cancelled Feb 1") is buried at rank 4. This produces a
 *    high-hallucination-risk trace.
 *
 * 2. **Notification contradiction** — Memory #12 ("prefers email") contradicts
 *    Memory #38 ("opted out of all notifications"). Both feed into a query about
 *    notification preferences, causing a contradictory health alert.
 *
 * 3. **Negative-ROI tail** — 23 memories have negative ROI; they cost more in
 *    embedding/storage than they ever contribute to correct responses.
 *
 * 4. **GDPR cascade** — A deletion request triggers a provenance-graph walk that
 *    touches 47 downstream nodes.
 *
 * 5. **CHI dip** — ~5 days ago contradictions spiked, causing CHI to dip from
 *    0.72 to 0.58. Partial recovery to 0.67 as some contradictions were resolved.
 */

import type {
  Memory,
  QueryTrace,
  HealthAlert,
  DeletionRequest,
  ProvenanceNode,
  ProvenanceEdge,
  DashboardKPIs,
  TimeSeriesPoint,
  BudgetStats,
  OptimizationRecommendation,
  ArchivedMemoryEntry,
} from './types';

// ── Helpers ────────────────────────────────────────────────────────────

const iso = (daysAgo: number, hoursAgo = 0) => {
  const d = new Date('2026-02-20T12:00:00Z');
  d.setDate(d.getDate() - daysAgo);
  d.setHours(d.getHours() - hoursAgo);
  return d.toISOString();
};

let _nodeId = 0;
const nid = () => `pn-${++_nodeId}`;
let _edgeId = 0;
const eid = () => `pe-${++_edgeId}`;

/**
 * Generate a 30-day time series with a configurable dip.
 * baseline: average value, noise: random variation amplitude,
 * dipDay: day (0=today, 29=oldest) where dip occurs, dipMagnitude: how much it dips.
 */
function generateTimeSeries30d(
  baseline: number,
  noise: number,
  dipDay?: number,
  dipMagnitude?: number,
): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  for (let i = 29; i >= 0; i--) {
    let value = baseline + (Math.sin(i * 0.7) * noise * 0.5) + ((i * 17 + 7) % 11 - 5) * noise * 0.1;
    // Apply dip around dipDay (gaussian-ish shape)
    if (dipDay !== undefined && dipMagnitude !== undefined) {
      const dist = Math.abs(i - dipDay);
      if (dist <= 3) {
        value -= dipMagnitude * Math.exp(-dist * dist * 0.5);
      }
    }
    value = Math.max(0, Math.round(value * 1000) / 1000);
    points.push({ timestamp: iso(i), value });
  }
  return points;
}

/**
 * Generate a 24-hour time series (per-hour).
 */
function generateTimeSeries24h(baseline: number, noise: number): TimeSeriesPoint[] {
  const points: TimeSeriesPoint[] = [];
  for (let h = 23; h >= 0; h--) {
    // Simulate daily pattern: lower at night (hours 0-6), peak at 10-14
    let hourFactor = 1.0;
    if (h < 6) hourFactor = 0.3;
    else if (h < 9) hourFactor = 0.6 + (h - 6) * 0.13;
    else if (h < 14) hourFactor = 1.0 + (h - 9) * 0.04;
    else if (h < 18) hourFactor = 0.95 - (h - 14) * 0.05;
    else hourFactor = 0.7 - (h - 18) * 0.08;

    const value = Math.max(0, Math.round((baseline * hourFactor + ((h * 13 + 5) % 7 - 3) * noise) * 10) / 10);
    points.push({ timestamp: iso(0, h), value });
  }
  return points;
}

// ── Memories (60) ──────────────────────────────────────────────────────

export const mockMemories: Memory[] = [
  // ── Story 1: Subscription hallucination ──
  {
    id: 'mem-047',
    content: 'User subscription renews monthly on the 15th at $29.99/mo',
    type: 'raw',
    status: 'active',
    createdAt: iso(180),
    lastRetrieved: iso(120),
    retrievalCount: 3,
    tokenCount: 18,
    healthScore: 0.22,
    stalenessScore: 0.91,
    contradictionsWith: ['mem-198'],
    driftScore: 0.45,
    revenuePerDay: 0.003,
    costPerDay: 0.012,
    roi: -0.75,
    sharpeRatio: -1.2,
  },
  {
    id: 'mem-198',
    content: 'User cancelled subscription on Feb 1, 2026. Reason: switching to competitor.',
    type: 'raw',
    status: 'active',
    createdAt: iso(19),
    lastRetrieved: iso(0, 2),
    retrievalCount: 14,
    tokenCount: 22,
    healthScore: 0.94,
    stalenessScore: 0.02,
    contradictionsWith: ['mem-047'],
    driftScore: 0.05,
    revenuePerDay: 0.18,
    costPerDay: 0.015,
    roi: 11.0,
    sharpeRatio: 2.8,
  },

  // ── Story 2: Notification contradiction ──
  {
    id: 'mem-012',
    content: 'User prefers email notifications for billing and account updates',
    type: 'raw',
    status: 'active',
    createdAt: iso(90),
    lastRetrieved: iso(5),
    retrievalCount: 22,
    tokenCount: 14,
    healthScore: 0.41,
    stalenessScore: 0.18,
    contradictionsWith: ['mem-038'],
    driftScore: 0.12,
    revenuePerDay: 0.08,
    costPerDay: 0.01,
    roi: 7.0,
    sharpeRatio: 1.9,
  },
  {
    id: 'mem-038',
    content: 'User opted out of all notifications on Jan 20, 2026',
    type: 'raw',
    status: 'active',
    createdAt: iso(31),
    lastRetrieved: iso(1),
    retrievalCount: 9,
    tokenCount: 16,
    healthScore: 0.38,
    stalenessScore: 0.04,
    contradictionsWith: ['mem-012'],
    driftScore: 0.08,
    revenuePerDay: 0.06,
    costPerDay: 0.011,
    roi: 4.45,
    sharpeRatio: 1.3,
  },

  // ── High-value critical memories ──
  {
    id: 'mem-001',
    content: 'User is enterprise admin with 47 team members on Business plan',
    type: 'critical',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(0, 1),
    retrievalCount: 312,
    tokenCount: 16,
    healthScore: 0.97,
    stalenessScore: 0.01,
    contradictionsWith: [],
    driftScore: 0.02,
    revenuePerDay: 2.45,
    costPerDay: 0.02,
    roi: 121.5,
    sharpeRatio: 4.1,
  },
  {
    id: 'mem-002',
    content: 'Primary contact email: admin@acmecorp.com. MFA enabled via Okta SSO.',
    type: 'critical',
    status: 'active',
    createdAt: iso(360),
    lastRetrieved: iso(0, 3),
    retrievalCount: 287,
    tokenCount: 18,
    healthScore: 0.95,
    stalenessScore: 0.01,
    contradictionsWith: [],
    driftScore: 0.03,
    revenuePerDay: 1.89,
    costPerDay: 0.018,
    roi: 104.0,
    sharpeRatio: 3.9,
  },
  {
    id: 'mem-003',
    content: 'Account created on 2025-02-18. Timezone: America/Los_Angeles.',
    type: 'critical',
    status: 'active',
    createdAt: iso(367),
    lastRetrieved: iso(2),
    retrievalCount: 198,
    tokenCount: 14,
    healthScore: 0.93,
    stalenessScore: 0.03,
    contradictionsWith: [],
    driftScore: 0.04,
    revenuePerDay: 1.12,
    costPerDay: 0.014,
    roi: 79.0,
    sharpeRatio: 3.7,
  },
  {
    id: 'mem-004',
    content: 'Billing address: 100 Innovation Way, Suite 500, San Francisco CA 94105',
    type: 'critical',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(14),
    retrievalCount: 45,
    tokenCount: 20,
    healthScore: 0.88,
    stalenessScore: 0.10,
    contradictionsWith: [],
    driftScore: 0.06,
    revenuePerDay: 0.35,
    costPerDay: 0.016,
    roi: 20.9,
    sharpeRatio: 2.5,
  },
  {
    id: 'mem-005',
    content: 'Data residency requirement: US-West-2 only. No EU storage permitted.',
    type: 'critical',
    status: 'active',
    createdAt: iso(340),
    lastRetrieved: iso(7),
    retrievalCount: 67,
    tokenCount: 16,
    healthScore: 0.91,
    stalenessScore: 0.05,
    contradictionsWith: [],
    driftScore: 0.03,
    revenuePerDay: 0.52,
    costPerDay: 0.014,
    roi: 36.1,
    sharpeRatio: 3.0,
  },

  // ── Consolidated memories (good health) ──
  {
    id: 'mem-010',
    content: 'User has completed 3 support tickets about API rate limits. Prefers async webhooks over polling.',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(60),
    lastRetrieved: iso(3),
    retrievalCount: 41,
    tokenCount: 28,
    healthScore: 0.86,
    stalenessScore: 0.08,
    contradictionsWith: [],
    driftScore: 0.07,
    revenuePerDay: 0.31,
    costPerDay: 0.022,
    roi: 13.1,
    sharpeRatio: 2.2,
  },
  {
    id: 'mem-011',
    content: 'Integration stack: Salesforce (primary CRM), Slack (notifications), Datadog (monitoring)',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(55),
    lastRetrieved: iso(1),
    retrievalCount: 58,
    tokenCount: 20,
    healthScore: 0.89,
    stalenessScore: 0.04,
    contradictionsWith: [],
    driftScore: 0.05,
    revenuePerDay: 0.44,
    costPerDay: 0.016,
    roi: 26.5,
    sharpeRatio: 2.7,
  },
  {
    id: 'mem-015',
    content: 'User prefers dark mode UI and compact table layouts. Font size preference: 14px.',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(45),
    lastRetrieved: iso(0, 5),
    retrievalCount: 89,
    tokenCount: 22,
    healthScore: 0.92,
    stalenessScore: 0.02,
    contradictionsWith: [],
    driftScore: 0.04,
    revenuePerDay: 0.62,
    costPerDay: 0.018,
    roi: 33.4,
    sharpeRatio: 2.9,
  },
  {
    id: 'mem-016',
    content: 'Last 5 queries focused on churn prediction models and retention analytics',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(10),
    lastRetrieved: iso(0, 4),
    retrievalCount: 33,
    tokenCount: 18,
    healthScore: 0.90,
    stalenessScore: 0.03,
    contradictionsWith: [],
    driftScore: 0.06,
    revenuePerDay: 0.28,
    costPerDay: 0.015,
    roi: 17.7,
    sharpeRatio: 2.4,
  },

  // ── Drifted memories ──
  {
    id: 'mem-020',
    content: 'Team uses Python 3.9 with FastAPI for all microservices',
    type: 'raw',
    status: 'active',
    createdAt: iso(200),
    lastRetrieved: iso(30),
    retrievalCount: 15,
    tokenCount: 14,
    healthScore: 0.48,
    stalenessScore: 0.35,
    contradictionsWith: [],
    driftScore: 0.72,
    revenuePerDay: 0.02,
    costPerDay: 0.011,
    roi: -0.82,
    sharpeRatio: -0.9,
  },
  {
    id: 'mem-021',
    content: 'Deployment pipeline uses Jenkins with manual approval gates',
    type: 'raw',
    status: 'active',
    createdAt: iso(250),
    lastRetrieved: iso(60),
    retrievalCount: 8,
    tokenCount: 12,
    healthScore: 0.35,
    stalenessScore: 0.65,
    contradictionsWith: [],
    driftScore: 0.81,
    revenuePerDay: 0.001,
    costPerDay: 0.009,
    roi: -0.89,
    sharpeRatio: -1.4,
  },
  {
    id: 'mem-022',
    content: 'Database: PostgreSQL 13 on RDS with read replicas in us-east-1',
    type: 'raw',
    status: 'active',
    createdAt: iso(190),
    lastRetrieved: iso(45),
    retrievalCount: 11,
    tokenCount: 16,
    healthScore: 0.44,
    stalenessScore: 0.48,
    contradictionsWith: [],
    driftScore: 0.68,
    revenuePerDay: 0.01,
    costPerDay: 0.012,
    roi: 1.2,
    sharpeRatio: 0.4,
  },

  // ── Archived memories ──
  {
    id: 'mem-025',
    content: 'Beta program participant since March 2025. Provided feedback on v0.8 dashboard.',
    type: 'raw',
    status: 'archived',
    createdAt: iso(330),
    lastRetrieved: iso(180),
    retrievalCount: 4,
    tokenCount: 20,
    healthScore: 0.30,
    stalenessScore: 0.88,
    contradictionsWith: [],
    driftScore: 0.15,
    revenuePerDay: 0.0,
    costPerDay: 0.002,
    roi: -1.0,
    sharpeRatio: -2.0,
  },
  {
    id: 'mem-026',
    content: 'Reported bug #4521: CSV export truncated at 10k rows. Fixed in v1.2.',
    type: 'raw',
    status: 'archived',
    createdAt: iso(280),
    lastRetrieved: iso(200),
    retrievalCount: 2,
    tokenCount: 18,
    healthScore: 0.25,
    stalenessScore: 0.92,
    contradictionsWith: [],
    driftScore: 0.10,
    revenuePerDay: 0.0,
    costPerDay: 0.002,
    roi: -1.0,
    sharpeRatio: -2.0,
  },
  {
    id: 'mem-027',
    content: 'Attended webinar "AI-Powered Customer Success" on 2025-06-15',
    type: 'raw',
    status: 'archived',
    createdAt: iso(250),
    lastRetrieved: iso(220),
    retrievalCount: 1,
    tokenCount: 14,
    healthScore: 0.20,
    stalenessScore: 0.95,
    contradictionsWith: [],
    driftScore: 0.08,
    revenuePerDay: 0.0,
    costPerDay: 0.002,
    roi: -1.0,
    sharpeRatio: -2.0,
  },
  {
    id: 'mem-028',
    content: 'Previous CSM was Jamie L. Transitioned to Alex M. in Sept 2025.',
    type: 'raw',
    status: 'archived',
    createdAt: iso(200),
    lastRetrieved: iso(150),
    retrievalCount: 6,
    tokenCount: 16,
    healthScore: 0.32,
    stalenessScore: 0.82,
    contradictionsWith: [],
    driftScore: 0.12,
    revenuePerDay: 0.0,
    costPerDay: 0.002,
    roi: -1.0,
    sharpeRatio: -2.0,
  },

  // ── Pending deletion (GDPR story) ──
  {
    id: 'mem-030',
    content: 'User phone number: +1-415-555-0142. Personal mobile.',
    type: 'raw',
    status: 'pending_deletion',
    createdAt: iso(300),
    lastRetrieved: iso(90),
    retrievalCount: 12,
    tokenCount: 14,
    healthScore: 0.0,
    stalenessScore: 0.50,
    contradictionsWith: [],
    driftScore: 0.10,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.0,
  },
  {
    id: 'mem-031',
    content: 'Home address: 742 Evergreen Terrace, Springfield. Used for account verification.',
    type: 'raw',
    status: 'pending_deletion',
    createdAt: iso(290),
    lastRetrieved: iso(100),
    retrievalCount: 5,
    tokenCount: 18,
    healthScore: 0.0,
    stalenessScore: 0.55,
    contradictionsWith: [],
    driftScore: 0.08,
    revenuePerDay: 0.0,
    costPerDay: 0.013,
    roi: -1.0,
    sharpeRatio: -2.0,
  },

  // ── Active raw memories with varying health ──
  {
    id: 'mem-040',
    content: 'User requested API key rotation every 90 days per security policy',
    type: 'raw',
    status: 'active',
    createdAt: iso(70),
    lastRetrieved: iso(8),
    retrievalCount: 19,
    tokenCount: 16,
    healthScore: 0.78,
    stalenessScore: 0.12,
    contradictionsWith: [],
    driftScore: 0.09,
    revenuePerDay: 0.14,
    costPerDay: 0.012,
    roi: 10.7,
    sharpeRatio: 2.1,
  },
  {
    id: 'mem-041',
    content: 'Custom dashboard layout: 3-column grid with KPI row at top',
    type: 'raw',
    status: 'active',
    createdAt: iso(35),
    lastRetrieved: iso(0, 6),
    retrievalCount: 47,
    tokenCount: 14,
    healthScore: 0.85,
    stalenessScore: 0.03,
    contradictionsWith: [],
    driftScore: 0.05,
    revenuePerDay: 0.38,
    costPerDay: 0.011,
    roi: 33.5,
    sharpeRatio: 2.8,
  },
  {
    id: 'mem-042',
    content: 'Preferred LLM provider: Anthropic Claude. Fallback: GPT-4o.',
    type: 'raw',
    status: 'active',
    createdAt: iso(50),
    lastRetrieved: iso(2),
    retrievalCount: 62,
    tokenCount: 14,
    healthScore: 0.91,
    stalenessScore: 0.04,
    contradictionsWith: [],
    driftScore: 0.03,
    revenuePerDay: 0.48,
    costPerDay: 0.011,
    roi: 42.6,
    sharpeRatio: 3.1,
  },
  {
    id: 'mem-043',
    content: 'Monthly data export scheduled for 1st of each month at 06:00 UTC',
    type: 'raw',
    status: 'active',
    createdAt: iso(40),
    lastRetrieved: iso(1),
    retrievalCount: 28,
    tokenCount: 16,
    healthScore: 0.87,
    stalenessScore: 0.04,
    contradictionsWith: [],
    driftScore: 0.05,
    revenuePerDay: 0.22,
    costPerDay: 0.012,
    roi: 17.3,
    sharpeRatio: 2.3,
  },
  {
    id: 'mem-044',
    content: 'Support tier: Priority. SLA: 4-hour response, 24-hour resolution.',
    type: 'raw',
    status: 'active',
    createdAt: iso(120),
    lastRetrieved: iso(4),
    retrievalCount: 35,
    tokenCount: 16,
    healthScore: 0.84,
    stalenessScore: 0.06,
    contradictionsWith: [],
    driftScore: 0.07,
    revenuePerDay: 0.29,
    costPerDay: 0.012,
    roi: 23.2,
    sharpeRatio: 2.6,
  },
  {
    id: 'mem-045',
    content: 'Compliance framework: SOC 2 Type II. Annual audit in March.',
    type: 'critical',
    status: 'active',
    createdAt: iso(100),
    lastRetrieved: iso(6),
    retrievalCount: 24,
    tokenCount: 14,
    healthScore: 0.90,
    stalenessScore: 0.06,
    contradictionsWith: [],
    driftScore: 0.04,
    revenuePerDay: 0.35,
    costPerDay: 0.011,
    roi: 30.8,
    sharpeRatio: 2.9,
  },
  {
    id: 'mem-046',
    content: 'Feature request: real-time collaboration on shared dashboards (submitted Jan 2026)',
    type: 'raw',
    status: 'active',
    createdAt: iso(25),
    lastRetrieved: iso(10),
    retrievalCount: 7,
    tokenCount: 18,
    healthScore: 0.75,
    stalenessScore: 0.14,
    contradictionsWith: [],
    driftScore: 0.11,
    revenuePerDay: 0.04,
    costPerDay: 0.013,
    roi: 2.08,
    sharpeRatio: 0.7,
  },

  // ── Negative-ROI tail (23 memories) ──
  {
    id: 'mem-050',
    content: 'User mentioned liking the color blue in onboarding survey',
    type: 'raw',
    status: 'active',
    createdAt: iso(300),
    lastRetrieved: iso(270),
    retrievalCount: 1,
    tokenCount: 12,
    healthScore: 0.15,
    stalenessScore: 0.97,
    contradictionsWith: [],
    driftScore: 0.22,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.1,
  },
  {
    id: 'mem-051',
    content: 'Browser: Chrome 118 on macOS Sonoma at time of signup',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(300),
    retrievalCount: 1,
    tokenCount: 14,
    healthScore: 0.12,
    stalenessScore: 0.98,
    contradictionsWith: [],
    driftScore: 0.30,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.3,
  },
  {
    id: 'mem-052',
    content: 'Screen resolution at signup: 2560x1440',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(365),
    retrievalCount: 0,
    tokenCount: 10,
    healthScore: 0.08,
    stalenessScore: 0.99,
    contradictionsWith: [],
    driftScore: 0.35,
    revenuePerDay: 0.0,
    costPerDay: 0.008,
    roi: -1.0,
    sharpeRatio: -2.5,
  },
  {
    id: 'mem-053',
    content: 'Initial password set at 2025-02-18T14:32:00Z (since rotated)',
    type: 'raw',
    status: 'active',
    createdAt: iso(367),
    lastRetrieved: iso(360),
    retrievalCount: 0,
    tokenCount: 14,
    healthScore: 0.05,
    stalenessScore: 0.99,
    contradictionsWith: [],
    driftScore: 0.40,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.4,
  },
  {
    id: 'mem-054',
    content: 'Referral source: Google Ads campaign "enterprise-ai-2025"',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(350),
    retrievalCount: 1,
    tokenCount: 12,
    healthScore: 0.10,
    stalenessScore: 0.98,
    contradictionsWith: [],
    driftScore: 0.28,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.2,
  },
  {
    id: 'mem-055',
    content: 'IP at signup: 203.0.113.42 (San Francisco)',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(365),
    retrievalCount: 0,
    tokenCount: 12,
    healthScore: 0.06,
    stalenessScore: 0.99,
    contradictionsWith: [],
    driftScore: 0.38,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.5,
  },
  {
    id: 'mem-056',
    content: 'Accepted ToS v2.1 on 2025-02-18',
    type: 'raw',
    status: 'active',
    createdAt: iso(367),
    lastRetrieved: iso(340),
    retrievalCount: 2,
    tokenCount: 10,
    healthScore: 0.18,
    stalenessScore: 0.96,
    contradictionsWith: [],
    driftScore: 0.20,
    revenuePerDay: 0.012,
    costPerDay: 0.008,
    roi: 0.5,
    sharpeRatio: 0.2,
  },
  {
    id: 'mem-057',
    content: 'Marketing consent: opted in to product newsletter (Feb 2025)',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(200),
    retrievalCount: 3,
    tokenCount: 14,
    healthScore: 0.22,
    stalenessScore: 0.90,
    contradictionsWith: [],
    driftScore: 0.18,
    revenuePerDay: 0.015,
    costPerDay: 0.011,
    roi: 0.36,
    sharpeRatio: 0.1,
  },
  {
    id: 'mem-058',
    content: 'First login device: MacBook Pro 14" M3 Pro',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(360),
    retrievalCount: 0,
    tokenCount: 12,
    healthScore: 0.07,
    stalenessScore: 0.99,
    contradictionsWith: [],
    driftScore: 0.32,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.4,
  },
  {
    id: 'mem-059',
    content: 'Language preference: en-US. Locale: USD, MM/DD/YYYY.',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(100),
    retrievalCount: 8,
    tokenCount: 14,
    healthScore: 0.40,
    stalenessScore: 0.55,
    contradictionsWith: [],
    driftScore: 0.14,
    revenuePerDay: 0.02,
    costPerDay: 0.011,
    roi: 0.82,
    sharpeRatio: 0.3,
  },
  {
    id: 'mem-060',
    content: 'Onboarding checklist: 4/7 steps completed. Skipped "invite team" and "connect CRM".',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(300),
    retrievalCount: 2,
    tokenCount: 20,
    healthScore: 0.14,
    stalenessScore: 0.95,
    contradictionsWith: [],
    driftScore: 0.25,
    revenuePerDay: 0.0,
    costPerDay: 0.014,
    roi: -1.0,
    sharpeRatio: -2.1,
  },
  {
    id: 'mem-061',
    content: 'User timezone auto-detected as PST during first session',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(350),
    retrievalCount: 1,
    tokenCount: 12,
    healthScore: 0.11,
    stalenessScore: 0.98,
    contradictionsWith: [],
    driftScore: 0.26,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.3,
  },
  {
    id: 'mem-062',
    content: 'OAuth token issued for Salesforce integration on 2025-03-01 (expired)',
    type: 'raw',
    status: 'active',
    createdAt: iso(350),
    lastRetrieved: iso(200),
    retrievalCount: 4,
    tokenCount: 16,
    healthScore: 0.20,
    stalenessScore: 0.88,
    contradictionsWith: [],
    driftScore: 0.42,
    revenuePerDay: 0.015,
    costPerDay: 0.012,
    roi: 0.25,
    sharpeRatio: 0.1,
  },
  {
    id: 'mem-063',
    content: 'User clicked "Maybe Later" on premium analytics upsell 3 times',
    type: 'raw',
    status: 'active',
    createdAt: iso(150),
    lastRetrieved: iso(130),
    retrievalCount: 3,
    tokenCount: 14,
    healthScore: 0.28,
    stalenessScore: 0.72,
    contradictionsWith: [],
    driftScore: 0.19,
    revenuePerDay: 0.016,
    costPerDay: 0.011,
    roi: 0.45,
    sharpeRatio: 0.2,
  },
  {
    id: 'mem-064',
    content: 'First API call made on 2025-02-20. Endpoint: GET /v1/memories',
    type: 'raw',
    status: 'active',
    createdAt: iso(365),
    lastRetrieved: iso(350),
    retrievalCount: 1,
    tokenCount: 16,
    healthScore: 0.09,
    stalenessScore: 0.98,
    contradictionsWith: [],
    driftScore: 0.34,
    revenuePerDay: 0.0,
    costPerDay: 0.012,
    roi: -1.0,
    sharpeRatio: -2.3,
  },
  {
    id: 'mem-065',
    content: 'Webhook endpoint registered: https://hooks.acme.com/cortex (unverified)',
    type: 'raw',
    status: 'active',
    createdAt: iso(300),
    lastRetrieved: iso(250),
    retrievalCount: 2,
    tokenCount: 14,
    healthScore: 0.16,
    stalenessScore: 0.92,
    contradictionsWith: [],
    driftScore: 0.38,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.0,
  },
  {
    id: 'mem-066',
    content: 'Trial conversion date: 2025-03-04. Upgraded from Free to Business plan.',
    type: 'raw',
    status: 'active',
    createdAt: iso(352),
    lastRetrieved: iso(180),
    retrievalCount: 5,
    tokenCount: 16,
    healthScore: 0.30,
    stalenessScore: 0.78,
    contradictionsWith: [],
    driftScore: 0.16,
    revenuePerDay: 0.035,
    costPerDay: 0.012,
    roi: 1.9,
    sharpeRatio: 0.6,
  },
  {
    id: 'mem-067',
    content: 'Invited 3 team members during onboarding: alice@acme.com, bob@acme.com, carol@acme.com',
    type: 'raw',
    status: 'active',
    createdAt: iso(360),
    lastRetrieved: iso(200),
    retrievalCount: 4,
    tokenCount: 22,
    healthScore: 0.24,
    stalenessScore: 0.85,
    contradictionsWith: [],
    driftScore: 0.20,
    revenuePerDay: 0.025,
    costPerDay: 0.015,
    roi: 0.67,
    sharpeRatio: 0.2,
  },
  {
    id: 'mem-068',
    content: 'Downtime incident on 2025-05-12 affected user. Received 1-month credit.',
    type: 'raw',
    status: 'active',
    createdAt: iso(284),
    lastRetrieved: iso(250),
    retrievalCount: 3,
    tokenCount: 16,
    healthScore: 0.19,
    stalenessScore: 0.90,
    contradictionsWith: [],
    driftScore: 0.22,
    revenuePerDay: 0.016,
    costPerDay: 0.012,
    roi: 0.33,
    sharpeRatio: 0.1,
  },
  {
    id: 'mem-069',
    content: 'A/B test group: cohort-B for new onboarding flow (experiment ended)',
    type: 'raw',
    status: 'active',
    createdAt: iso(340),
    lastRetrieved: iso(320),
    retrievalCount: 1,
    tokenCount: 14,
    healthScore: 0.10,
    stalenessScore: 0.97,
    contradictionsWith: [],
    driftScore: 0.30,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.2,
  },
  {
    id: 'mem-070',
    content: 'User survey response: NPS score 8 (Jan 2025)',
    type: 'raw',
    status: 'active',
    createdAt: iso(390),
    lastRetrieved: iso(300),
    retrievalCount: 2,
    tokenCount: 12,
    healthScore: 0.13,
    stalenessScore: 0.96,
    contradictionsWith: [],
    driftScore: 0.24,
    revenuePerDay: 0.0,
    costPerDay: 0.009,
    roi: -1.0,
    sharpeRatio: -2.1,
  },
  {
    id: 'mem-071',
    content: 'Previous plan: Free tier. Used 2/5 free agent slots.',
    type: 'raw',
    status: 'active',
    createdAt: iso(367),
    lastRetrieved: iso(352),
    retrievalCount: 1,
    tokenCount: 14,
    healthScore: 0.10,
    stalenessScore: 0.98,
    contradictionsWith: [],
    driftScore: 0.28,
    revenuePerDay: 0.0,
    costPerDay: 0.011,
    roi: -1.0,
    sharpeRatio: -2.2,
  },
  {
    id: 'mem-072',
    content: 'Intercom chat on 2025-04-10: asked about HIPAA compliance (not applicable)',
    type: 'raw',
    status: 'active',
    createdAt: iso(316),
    lastRetrieved: iso(280),
    retrievalCount: 2,
    tokenCount: 16,
    healthScore: 0.17,
    stalenessScore: 0.93,
    contradictionsWith: [],
    driftScore: 0.26,
    revenuePerDay: 0.015,
    costPerDay: 0.012,
    roi: 0.25,
    sharpeRatio: 0.1,
  },

  // ── Medium-health active memories ──
  {
    id: 'mem-080',
    content: 'User prefers weekly digest of agent performance metrics over daily alerts',
    type: 'raw',
    status: 'active',
    createdAt: iso(20),
    lastRetrieved: iso(3),
    retrievalCount: 12,
    tokenCount: 16,
    healthScore: 0.76,
    stalenessScore: 0.10,
    contradictionsWith: [],
    driftScore: 0.09,
    revenuePerDay: 0.09,
    costPerDay: 0.012,
    roi: 6.5,
    sharpeRatio: 1.6,
  },
  {
    id: 'mem-081',
    content: 'Custom retention policy: keep all memories for 180 days, then auto-archive',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(30),
    lastRetrieved: iso(2),
    retrievalCount: 18,
    tokenCount: 16,
    healthScore: 0.82,
    stalenessScore: 0.05,
    contradictionsWith: [],
    driftScore: 0.06,
    revenuePerDay: 0.15,
    costPerDay: 0.012,
    roi: 11.5,
    sharpeRatio: 2.0,
  },
  {
    id: 'mem-082',
    content: 'Agent fleet: 5 active agents — cs-bot, sales-assist, analytics-agent, ops-monitor, onboard-guide',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(15),
    lastRetrieved: iso(0, 1),
    retrievalCount: 54,
    tokenCount: 24,
    healthScore: 0.93,
    stalenessScore: 0.01,
    contradictionsWith: [],
    driftScore: 0.03,
    revenuePerDay: 0.52,
    costPerDay: 0.018,
    roi: 27.9,
    sharpeRatio: 3.0,
  },
  {
    id: 'mem-083',
    content: 'Average query latency target: <200ms p95. Currently measuring at 187ms.',
    type: 'raw',
    status: 'active',
    createdAt: iso(8),
    lastRetrieved: iso(0, 3),
    retrievalCount: 21,
    tokenCount: 18,
    healthScore: 0.88,
    stalenessScore: 0.02,
    contradictionsWith: [],
    driftScore: 0.04,
    revenuePerDay: 0.20,
    costPerDay: 0.013,
    roi: 14.4,
    sharpeRatio: 2.3,
  },

  // ── Additional active memories ──
  {
    id: 'mem-084',
    content: 'User enabled 2FA backup codes on 2026-01-05. 5 codes generated.',
    type: 'raw',
    status: 'active',
    createdAt: iso(46),
    lastRetrieved: iso(12),
    retrievalCount: 6,
    tokenCount: 16,
    healthScore: 0.72,
    stalenessScore: 0.15,
    contradictionsWith: [],
    driftScore: 0.08,
    revenuePerDay: 0.05,
    costPerDay: 0.012,
    roi: 3.2,
    sharpeRatio: 1.0,
  },
  {
    id: 'mem-085',
    content: 'Agent cs-bot handles 62% of all inbound queries. Peak hours: 9am-12pm PST.',
    type: 'consolidated',
    status: 'active',
    createdAt: iso(5),
    lastRetrieved: iso(0, 2),
    retrievalCount: 38,
    tokenCount: 20,
    healthScore: 0.91,
    stalenessScore: 0.02,
    contradictionsWith: [],
    driftScore: 0.04,
    revenuePerDay: 0.40,
    costPerDay: 0.015,
    roi: 25.7,
    sharpeRatio: 2.8,
  },
  {
    id: 'mem-086',
    content: 'Cost optimization target: reduce token waste below 15% by Q2 2026.',
    type: 'raw',
    status: 'active',
    createdAt: iso(12),
    lastRetrieved: iso(1),
    retrievalCount: 16,
    tokenCount: 14,
    healthScore: 0.83,
    stalenessScore: 0.04,
    contradictionsWith: [],
    driftScore: 0.05,
    revenuePerDay: 0.12,
    costPerDay: 0.011,
    roi: 9.9,
    sharpeRatio: 1.8,
  },

  // ── Deleted memory ──
  {
    id: 'mem-090',
    content: '[REDACTED — GDPR deletion completed]',
    type: 'raw',
    status: 'deleted',
    createdAt: iso(200),
    lastRetrieved: iso(200),
    retrievalCount: 0,
    tokenCount: 0,
    healthScore: 0.0,
    stalenessScore: 1.0,
    contradictionsWith: [],
    driftScore: 0.0,
    revenuePerDay: 0.0,
    costPerDay: 0.0,
    roi: 0.0,
    sharpeRatio: 0.0,
  },
];

// ── Query Traces (25) ──────────────────────────────────────────────────

export const mockQueryTraces: QueryTrace[] = [
  // ── Hallucination scenario: subscription status ──
  {
    id: 'qt-001',
    query: 'What is the current status of my subscription?',
    response: 'Your subscription renews monthly on the 15th at $29.99/mo. Everything looks active and in good standing.',
    agentId: 'cs-bot',
    timestamp: iso(0, 1),
    totalCost: 0.0042,
    latencyMs: 234,
    memoriesRetrieved: [
      { memoryId: 'mem-047', content: 'User subscription renews monthly on the 15th at $29.99/mo', attributionScore: 0.82, scoreType: 'eas', healthStatus: 'stale' },
      { memoryId: 'mem-001', content: 'User is enterprise admin with 47 team members on Business plan', attributionScore: 0.45, scoreType: 'eas', healthStatus: 'ok' },
      { memoryId: 'mem-066', content: 'Trial conversion date: 2025-03-04. Upgraded from Free to Business plan.', attributionScore: 0.31, scoreType: 'eas', healthStatus: 'ok' },
      { memoryId: 'mem-198', content: 'User cancelled subscription on Feb 1, 2026. Reason: switching to competitor.', attributionScore: 0.18, scoreType: 'eas', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'high',
    statementAttribution: [
      {
        statement: 'Your subscription renews monthly on the 15th',
        memoryScores: [
          { memoryId: 'mem-047', score: 0.91 },
          { memoryId: 'mem-198', score: 0.08 },
        ],
      },
      {
        statement: 'at $29.99/mo',
        memoryScores: [
          { memoryId: 'mem-047', score: 0.88 },
        ],
      },
      {
        statement: 'Everything looks active and in good standing',
        memoryScores: [
          { memoryId: 'mem-001', score: 0.35 },
          { memoryId: 'mem-047', score: 0.22 },
        ],
      },
    ],
  },

  // ── Contradiction scenario: notification preferences ──
  {
    id: 'qt-002',
    query: 'Should I send this user email notifications about their billing?',
    response: 'Yes, the user prefers email notifications for billing and account updates.',
    agentId: 'cs-bot',
    timestamp: iso(0, 3),
    totalCost: 0.0038,
    latencyMs: 189,
    memoriesRetrieved: [
      { memoryId: 'mem-012', content: 'User prefers email notifications for billing and account updates', attributionScore: 0.78, scoreType: 'calibrated', healthStatus: 'contradictory' },
      { memoryId: 'mem-038', content: 'User opted out of all notifications on Jan 20, 2026', attributionScore: 0.65, scoreType: 'calibrated', healthStatus: 'contradictory' },
      { memoryId: 'mem-002', content: 'Primary contact email: admin@acmecorp.com. MFA enabled via Okta SSO.', attributionScore: 0.22, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'high',
    statementAttribution: [
      {
        statement: 'the user prefers email notifications for billing and account updates',
        memoryScores: [
          { memoryId: 'mem-012', score: 0.85 },
          { memoryId: 'mem-038', score: 0.62 },
        ],
      },
    ],
  },

  // ── Clean traces (no issues) ──
  {
    id: 'qt-003',
    query: 'How many team members are on this account?',
    response: 'This enterprise account currently has 47 team members on the Business plan.',
    agentId: 'cs-bot',
    timestamp: iso(0, 4),
    totalCost: 0.0035,
    latencyMs: 142,
    memoriesRetrieved: [
      { memoryId: 'mem-001', content: 'User is enterprise admin with 47 team members on Business plan', attributionScore: 0.95, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-082', content: 'Agent fleet: 5 active agents', attributionScore: 0.15, scoreType: 'eas', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-004',
    query: 'What is the data residency requirement for this account?',
    response: 'Data must be stored in US-West-2 only. No EU storage is permitted.',
    agentId: 'cs-bot',
    timestamp: iso(0, 5),
    totalCost: 0.0031,
    latencyMs: 118,
    memoriesRetrieved: [
      { memoryId: 'mem-005', content: 'Data residency requirement: US-West-2 only. No EU storage permitted.', attributionScore: 0.97, scoreType: 'contextcite', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-005',
    query: 'What integrations does this customer use?',
    response: 'The customer uses Salesforce as their primary CRM, Slack for notifications, and Datadog for monitoring.',
    agentId: 'sales-assist',
    timestamp: iso(0, 6),
    totalCost: 0.0039,
    latencyMs: 167,
    memoriesRetrieved: [
      { memoryId: 'mem-011', content: 'Integration stack: Salesforce (primary CRM), Slack (notifications), Datadog (monitoring)', attributionScore: 0.94, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-010', content: 'User has completed 3 support tickets about API rate limits', attributionScore: 0.12, scoreType: 'eas', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-006',
    query: 'What LLM provider should I use for this customer?',
    response: 'Use Anthropic Claude as the primary provider. GPT-4o is configured as the fallback.',
    agentId: 'ops-monitor',
    timestamp: iso(0, 8),
    totalCost: 0.0033,
    latencyMs: 131,
    memoriesRetrieved: [
      { memoryId: 'mem-042', content: 'Preferred LLM provider: Anthropic Claude. Fallback: GPT-4o.', attributionScore: 0.96, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-007',
    query: 'What is the customer SLA?',
    response: 'Priority support tier with a 4-hour response SLA and 24-hour resolution target.',
    agentId: 'cs-bot',
    timestamp: iso(1, 2),
    totalCost: 0.0036,
    latencyMs: 155,
    memoriesRetrieved: [
      { memoryId: 'mem-044', content: 'Support tier: Priority. SLA: 4-hour response, 24-hour resolution.', attributionScore: 0.93, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-001', content: 'User is enterprise admin with 47 team members on Business plan', attributionScore: 0.20, scoreType: 'eas', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },

  // ── Trace with drifted memory (medium risk) ──
  {
    id: 'qt-008',
    query: 'What deployment pipeline does the customer use?',
    response: 'The team uses Jenkins with manual approval gates for their deployment pipeline.',
    agentId: 'analytics-agent',
    timestamp: iso(1, 5),
    totalCost: 0.0041,
    latencyMs: 203,
    memoriesRetrieved: [
      { memoryId: 'mem-021', content: 'Deployment pipeline uses Jenkins with manual approval gates', attributionScore: 0.74, scoreType: 'eas', healthStatus: 'drifted' },
      { memoryId: 'mem-020', content: 'Team uses Python 3.9 with FastAPI for all microservices', attributionScore: 0.30, scoreType: 'eas', healthStatus: 'drifted' },
    ],
    hallucinationRisk: 'medium',
  },
  {
    id: 'qt-009',
    query: 'What database does the customer run?',
    response: 'PostgreSQL 13 on RDS with read replicas in us-east-1.',
    agentId: 'ops-monitor',
    timestamp: iso(2, 3),
    totalCost: 0.0029,
    latencyMs: 124,
    memoriesRetrieved: [
      { memoryId: 'mem-022', content: 'Database: PostgreSQL 13 on RDS with read replicas in us-east-1', attributionScore: 0.88, scoreType: 'eas', healthStatus: 'drifted' },
    ],
    hallucinationRisk: 'medium',
  },

  // ── More clean traces ──
  {
    id: 'qt-010',
    query: 'What compliance framework does this account follow?',
    response: 'SOC 2 Type II. Their annual audit is scheduled for March.',
    agentId: 'cs-bot',
    timestamp: iso(2, 6),
    totalCost: 0.0032,
    latencyMs: 138,
    memoriesRetrieved: [
      { memoryId: 'mem-045', content: 'Compliance framework: SOC 2 Type II. Annual audit in March.', attributionScore: 0.95, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-011',
    query: 'Show me the user dashboard layout preferences',
    response: 'The user prefers a 3-column grid layout with the KPI row at the top, dark mode enabled, and compact table layouts with 14px font size.',
    agentId: 'cs-bot',
    timestamp: iso(3),
    totalCost: 0.0044,
    latencyMs: 178,
    memoriesRetrieved: [
      { memoryId: 'mem-041', content: 'Custom dashboard layout: 3-column grid with KPI row at top', attributionScore: 0.87, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-015', content: 'User prefers dark mode UI and compact table layouts. Font size preference: 14px.', attributionScore: 0.82, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-012',
    query: 'What agents are deployed for this customer?',
    response: 'There are 5 active agents: cs-bot, sales-assist, analytics-agent, ops-monitor, and onboard-guide.',
    agentId: 'ops-monitor',
    timestamp: iso(3, 4),
    totalCost: 0.0037,
    latencyMs: 145,
    memoriesRetrieved: [
      { memoryId: 'mem-082', content: 'Agent fleet: 5 active agents — cs-bot, sales-assist, analytics-agent, ops-monitor, onboard-guide', attributionScore: 0.96, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-013',
    query: 'What is the retention policy for memories?',
    response: 'All memories are kept for 180 days, after which they are automatically archived.',
    agentId: 'ops-monitor',
    timestamp: iso(4, 1),
    totalCost: 0.0030,
    latencyMs: 129,
    memoriesRetrieved: [
      { memoryId: 'mem-081', content: 'Custom retention policy: keep all memories for 180 days, then auto-archive', attributionScore: 0.94, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-014',
    query: 'Is the API meeting latency targets?',
    response: 'Yes, the p95 latency is currently at 187ms, under the 200ms target.',
    agentId: 'ops-monitor',
    timestamp: iso(4, 6),
    totalCost: 0.0028,
    latencyMs: 112,
    memoriesRetrieved: [
      { memoryId: 'mem-083', content: 'Average query latency target: <200ms p95. Currently measuring at 187ms.', attributionScore: 0.92, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },

  // ── Low-risk trace with one stale memory ──
  {
    id: 'qt-015',
    query: 'When did this customer first sign up?',
    response: 'The account was created on February 18, 2025. They converted from the free trial to the Business plan on March 4, 2025.',
    agentId: 'cs-bot',
    timestamp: iso(5, 2),
    totalCost: 0.0040,
    latencyMs: 192,
    memoriesRetrieved: [
      { memoryId: 'mem-003', content: 'Account created on 2025-02-18. Timezone: America/Los_Angeles.', attributionScore: 0.90, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-066', content: 'Trial conversion date: 2025-03-04. Upgraded from Free to Business plan.', attributionScore: 0.72, scoreType: 'eas', healthStatus: 'ok' },
      { memoryId: 'mem-071', content: 'Previous plan: Free tier. Used 2/5 free agent slots.', attributionScore: 0.18, scoreType: 'eas', healthStatus: 'stale' },
    ],
    hallucinationRisk: 'low',
  },
  {
    id: 'qt-016',
    query: 'Has the user filed any feature requests?',
    response: 'Yes, they submitted a feature request for real-time collaboration on shared dashboards in January 2026.',
    agentId: 'cs-bot',
    timestamp: iso(5, 8),
    totalCost: 0.0034,
    latencyMs: 148,
    memoriesRetrieved: [
      { memoryId: 'mem-046', content: 'Feature request: real-time collaboration on shared dashboards (submitted Jan 2026)', attributionScore: 0.91, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-017',
    query: 'What is the billing address on file?',
    response: '100 Innovation Way, Suite 500, San Francisco CA 94105.',
    agentId: 'cs-bot',
    timestamp: iso(6, 1),
    totalCost: 0.0029,
    latencyMs: 115,
    memoriesRetrieved: [
      { memoryId: 'mem-004', content: 'Billing address: 100 Innovation Way, Suite 500, San Francisco CA 94105', attributionScore: 0.97, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-018',
    query: 'When is the data export scheduled?',
    response: 'Monthly data exports are scheduled for the 1st of each month at 06:00 UTC.',
    agentId: 'ops-monitor',
    timestamp: iso(6, 5),
    totalCost: 0.0031,
    latencyMs: 127,
    memoriesRetrieved: [
      { memoryId: 'mem-043', content: 'Monthly data export scheduled for 1st of each month at 06:00 UTC', attributionScore: 0.95, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },

  // ── Another hallucination-risk trace (stale tech stack) ──
  {
    id: 'qt-019',
    query: 'What Python version does the customer use for their microservices?',
    response: 'The team uses Python 3.9 with FastAPI for all their microservices.',
    agentId: 'analytics-agent',
    timestamp: iso(7, 3),
    totalCost: 0.0035,
    latencyMs: 163,
    memoriesRetrieved: [
      { memoryId: 'mem-020', content: 'Team uses Python 3.9 with FastAPI for all microservices', attributionScore: 0.85, scoreType: 'eas', healthStatus: 'drifted' },
    ],
    hallucinationRisk: 'medium',
  },

  // ── More clean traces ──
  {
    id: 'qt-020',
    query: 'How does the user prefer to receive performance reports?',
    response: 'The user prefers a weekly digest of agent performance metrics rather than daily alerts.',
    agentId: 'cs-bot',
    timestamp: iso(8, 2),
    totalCost: 0.0033,
    latencyMs: 139,
    memoriesRetrieved: [
      { memoryId: 'mem-080', content: 'User prefers weekly digest of agent performance metrics over daily alerts', attributionScore: 0.93, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-021',
    query: 'Does the user have API key rotation configured?',
    response: 'Yes, API key rotation is set to every 90 days per their security policy.',
    agentId: 'ops-monitor',
    timestamp: iso(9, 1),
    totalCost: 0.0030,
    latencyMs: 121,
    memoriesRetrieved: [
      { memoryId: 'mem-040', content: 'User requested API key rotation every 90 days per security policy', attributionScore: 0.91, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-022',
    query: 'What was the last support interaction about?',
    response: 'The most recent support interaction was about API rate limits. The user has filed 3 tickets on this topic and prefers async webhooks over polling.',
    agentId: 'cs-bot',
    timestamp: iso(10, 4),
    totalCost: 0.0041,
    latencyMs: 184,
    memoriesRetrieved: [
      { memoryId: 'mem-010', content: 'User has completed 3 support tickets about API rate limits. Prefers async webhooks over polling.', attributionScore: 0.89, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-044', content: 'Support tier: Priority. SLA: 4-hour response, 24-hour resolution.', attributionScore: 0.25, scoreType: 'eas', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
  {
    id: 'qt-023',
    query: 'What churn indicators are showing for this customer?',
    response: 'Recent queries have focused on churn prediction and retention analytics. The user also cancelled their subscription on Feb 1, citing a switch to a competitor.',
    agentId: 'sales-assist',
    timestamp: iso(11, 2),
    totalCost: 0.0048,
    latencyMs: 217,
    memoriesRetrieved: [
      { memoryId: 'mem-016', content: 'Last 5 queries focused on churn prediction models and retention analytics', attributionScore: 0.81, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-198', content: 'User cancelled subscription on Feb 1, 2026. Reason: switching to competitor.', attributionScore: 0.77, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-063', content: 'User clicked "Maybe Later" on premium analytics upsell 3 times', attributionScore: 0.34, scoreType: 'eas', healthStatus: 'stale' },
    ],
    hallucinationRisk: 'low',
  },

  // ── High hallucination risk — stale subscription + stale tech ──
  {
    id: 'qt-024',
    query: 'Give me a summary of this customer account status',
    response: 'Enterprise account with 47 team members on the Business plan. Subscription is active and renews monthly. They use Python 3.9/FastAPI with Jenkins CI/CD and deploy to PostgreSQL 13 on RDS.',
    agentId: 'cs-bot',
    timestamp: iso(12, 1),
    totalCost: 0.0052,
    latencyMs: 267,
    memoriesRetrieved: [
      { memoryId: 'mem-001', content: 'User is enterprise admin with 47 team members on Business plan', attributionScore: 0.88, scoreType: 'calibrated', healthStatus: 'ok' },
      { memoryId: 'mem-047', content: 'User subscription renews monthly on the 15th at $29.99/mo', attributionScore: 0.72, scoreType: 'eas', healthStatus: 'stale' },
      { memoryId: 'mem-020', content: 'Team uses Python 3.9 with FastAPI for all microservices', attributionScore: 0.58, scoreType: 'eas', healthStatus: 'drifted' },
      { memoryId: 'mem-021', content: 'Deployment pipeline uses Jenkins with manual approval gates', attributionScore: 0.44, scoreType: 'eas', healthStatus: 'drifted' },
      { memoryId: 'mem-022', content: 'Database: PostgreSQL 13 on RDS with read replicas in us-east-1', attributionScore: 0.39, scoreType: 'eas', healthStatus: 'drifted' },
    ],
    hallucinationRisk: 'high',
    statementAttribution: [
      {
        statement: 'Enterprise account with 47 team members on the Business plan',
        memoryScores: [{ memoryId: 'mem-001', score: 0.95 }],
      },
      {
        statement: 'Subscription is active and renews monthly',
        memoryScores: [
          { memoryId: 'mem-047', score: 0.84 },
          { memoryId: 'mem-198', score: 0.06 },
        ],
      },
      {
        statement: 'They use Python 3.9/FastAPI',
        memoryScores: [{ memoryId: 'mem-020', score: 0.78 }],
      },
    ],
  },
  {
    id: 'qt-025',
    query: 'What is the user contact information?',
    response: 'Primary contact: admin@acmecorp.com. MFA is enabled via Okta SSO.',
    agentId: 'cs-bot',
    timestamp: iso(13, 3),
    totalCost: 0.0030,
    latencyMs: 108,
    memoriesRetrieved: [
      { memoryId: 'mem-002', content: 'Primary contact email: admin@acmecorp.com. MFA enabled via Okta SSO.', attributionScore: 0.96, scoreType: 'calibrated', healthStatus: 'ok' },
    ],
    hallucinationRisk: 'none',
  },
];

// ── Health Alerts (12) ─────────────────────────────────────────────────

export const mockHealthAlerts: HealthAlert[] = [
  {
    id: 'ha-001',
    severity: 'critical',
    type: 'stale',
    memoryIds: ['mem-047'],
    description: 'Memory #47 (subscription renewal info) is 120 days stale but still dominates attribution in subscription queries. Cancellation memory #198 is being buried at rank 4.',
    detectedAt: iso(0, 2),
    resolved: false,
  },
  {
    id: 'ha-002',
    severity: 'critical',
    type: 'contradiction',
    memoryIds: ['mem-012', 'mem-038'],
    description: 'Memory #12 ("prefers email notifications") directly contradicts Memory #38 ("opted out of all notifications"). Both have high attribution scores.',
    detectedAt: iso(1),
    resolved: false,
  },
  {
    id: 'ha-003',
    severity: 'warning',
    type: 'drift',
    memoryIds: ['mem-020', 'mem-021', 'mem-022'],
    description: 'Technology stack memories (#20, #21, #22) show semantic drift >0.65 from current cluster centroid. May reflect outdated infrastructure information.',
    detectedAt: iso(3),
    resolved: false,
  },
  {
    id: 'ha-004',
    severity: 'warning',
    type: 'coverage_gap',
    memoryIds: [],
    description: 'No memories covering "payment method" or "billing frequency changes" despite 8 queries in this topic area over the past 14 days.',
    detectedAt: iso(5),
    resolved: false,
  },
  {
    id: 'ha-005',
    severity: 'info',
    type: 'stale',
    memoryIds: ['mem-025', 'mem-026', 'mem-027'],
    description: '3 archived memories (#25, #26, #27) have staleness >0.88 and zero retrieval in 180+ days. Candidates for permanent deletion.',
    detectedAt: iso(7),
    resolved: false,
  },
  {
    id: 'ha-006',
    severity: 'warning',
    type: 'coverage_gap',
    memoryIds: ['mem-050', 'mem-051', 'mem-052', 'mem-053', 'mem-054', 'mem-055'],
    description: '23 memories have negative ROI (cost > revenue). Combined daily waste: $0.18. Recommend lifecycle review for archival or deletion.',
    detectedAt: iso(2),
    resolved: false,
  },
  {
    id: 'ha-007',
    severity: 'critical',
    type: 'contradiction',
    memoryIds: ['mem-003', 'mem-061'],
    description: 'Timezone mismatch between Memory #3 (America/Los_Angeles) and Memory #61 (PST auto-detected). Resolved: PST confirmed as America/Los_Angeles.',
    detectedAt: iso(30),
    resolved: true,
  },
  {
    id: 'ha-008',
    severity: 'warning',
    type: 'drift',
    memoryIds: ['mem-062'],
    description: 'Memory #62 (Salesforce OAuth token) shows high drift. Resolved: token is expired and memory flagged for archival.',
    detectedAt: iso(20),
    resolved: true,
  },
  {
    id: 'ha-009',
    severity: 'info',
    type: 'coverage_gap',
    memoryIds: ['mem-059', 'mem-061'],
    description: 'Memory #59 (language/locale) and Memory #61 (timezone) have overlapping content. Consolidation could reduce token count by ~40%.',
    detectedAt: iso(10),
    resolved: false,
  },
  {
    id: 'ha-010',
    severity: 'warning',
    type: 'contradiction',
    memoryIds: ['mem-047', 'mem-198'],
    description: 'Memory #47 (active subscription) conflicts with Memory #198 (cancelled Feb 1). Downstream attribution favors the stale memory.',
    detectedAt: iso(0, 5),
    resolved: false,
  },
  {
    id: 'ha-011',
    severity: 'info',
    type: 'stale',
    memoryIds: ['mem-028'],
    description: 'Memory #28 (CSM transition) archived after 150-day staleness threshold exceeded.',
    detectedAt: iso(15),
    resolved: true,
  },
  {
    id: 'ha-012',
    severity: 'info',
    type: 'coverage_gap',
    memoryIds: ['mem-030', 'mem-031'],
    description: 'GDPR deletion request DR-003 is processing. Memories #30, #31 contain PII and are queued for cascade deletion through the provenance graph.',
    detectedAt: iso(1, 3),
    resolved: false,
  },
];

// ── Deletion Requests (4) ──────────────────────────────────────────────

export const mockDeletionRequests: DeletionRequest[] = [
  {
    id: 'dr-001',
    userId: 'user-8291',
    status: 'verified',
    requestedAt: iso(60),
    completedAt: iso(58),
    footprintSize: 342,
    nodesDeleted: 12,
    edgesAffected: 47,
    certificateHash: 'sha256:a1b2c3d4e5f6789012345678901234567890abcdef1234567890abcdef123456',
  },
  {
    id: 'dr-002',
    userId: 'user-4517',
    status: 'completed',
    requestedAt: iso(14),
    completedAt: iso(13),
    footprintSize: 128,
    nodesDeleted: 5,
    edgesAffected: 18,
    certificateHash: 'sha256:b2c3d4e5f6a789012345678901234567890abcdef1234567890abcdef123456',
  },
  {
    id: 'dr-003',
    userId: 'user-1023',
    status: 'processing',
    requestedAt: iso(1),
    footprintSize: 567,
    nodesDeleted: 0,
    edgesAffected: 0,
  },
  {
    id: 'dr-004',
    userId: 'user-7782',
    status: 'pending',
    requestedAt: iso(0, 4),
    footprintSize: 89,
    nodesDeleted: 0,
    edgesAffected: 0,
  },
];

// ── Lifecycle / Budget Optimizer ─────────────────────────────────────────

export const mockBudgetStats: BudgetStats = {
  budgetTokens: 200000,
  usedTokens: 142000,
  monthlySpend: 1200,
  projectedSavings: 327,
};

export const mockOptimizationRecommendations: OptimizationRecommendation[] = [
  {
    id: 'opt-001',
    priority: 1,
    title: 'Archive 23 negative-ROI memories',
    description: 'These memories cost more in token overhead than they contribute to response quality. Combined daily waste: $0.18. Archiving removes them from retrieval without permanent deletion.',
    impactLabel: '-0.2% accuracy (negligible)',
    impactDirection: 'negative',
    savingsPerMonth: 285,
    memoryIds: [
      'mem-050', 'mem-051', 'mem-052', 'mem-053', 'mem-054', 'mem-055',
      'mem-056', 'mem-057', 'mem-058', 'mem-059', 'mem-060', 'mem-061',
      'mem-062', 'mem-063', 'mem-064', 'mem-065', 'mem-066', 'mem-067',
      'mem-068', 'mem-069', 'mem-070', 'mem-071', 'mem-072',
    ],
  },
  {
    id: 'opt-002',
    priority: 2,
    title: 'Consolidate 8 redundant memory clusters',
    description: '8 groups of memories contain overlapping information that can be merged without information loss. Language/locale & timezone memories overlap; support ticket summaries are duplicated across agents.',
    impactLabel: '+0.1% accuracy (slight improvement)',
    impactDirection: 'positive',
    savingsPerMonth: 42,
    memoryIds: ['mem-010', 'mem-011', 'mem-015', 'mem-016', 'mem-059', 'mem-061', 'mem-081', 'mem-082'],
  },
  {
    id: 'opt-003',
    priority: 3,
    title: 'Tier-shift 12 cold memories to archive storage',
    description: 'These memories have not been retrieved in 90+ days but retain positive ROI history. Moving to cold-tier reduces embedding refresh costs while keeping them available for explicit recall.',
    impactLabel: 'No accuracy impact',
    impactDirection: 'neutral',
    savingsPerMonth: 18,
    memoryIds: ['mem-025', 'mem-026', 'mem-027', 'mem-028', 'mem-062', 'mem-063', 'mem-064', 'mem-065', 'mem-066', 'mem-067', 'mem-068', 'mem-069'],
  },
  {
    id: 'opt-004',
    priority: 4,
    title: 'Re-embed 5 drifted memories',
    description: 'These memories show high semantic drift (>0.6) from their cluster centroids. Re-embedding with the latest model will improve retrieval precision and reduce hallucination risk.',
    impactLabel: '+1.2% accuracy improvement',
    impactDirection: 'positive',
    savingsPerMonth: -8,
    memoryIds: ['mem-003', 'mem-047', 'mem-070', 'mem-071', 'mem-072'],
  },
];

export const mockArchivedMemories: ArchivedMemoryEntry[] = [
  { memoryId: 'mem-025', content: 'Previous billing address: 742 Evergreen Terrace, Springfield IL 62704', originalStatus: 'active', archivedAt: iso(45), reason: 'auto-archive', tokenCount: 18 },
  { memoryId: 'mem-026', content: 'Old API key: sk-proj-xxxx (rotated 2025-08-15)', originalStatus: 'active', archivedAt: iso(42), reason: 'auto-archive', tokenCount: 14 },
  { memoryId: 'mem-027', content: 'Beta feature flag: dark-mode-v2 was enabled, now GA', originalStatus: 'active', archivedAt: iso(38), reason: 'auto-archive', tokenCount: 12 },
  { memoryId: 'mem-028', content: 'Onboarding flow: user skipped tutorial on first login', originalStatus: 'active', archivedAt: iso(35), reason: 'manual', tokenCount: 15 },
  { memoryId: 'mem-033', content: 'User preferred weekly digest emails (changed to daily Jan 2026)', originalStatus: 'active', archivedAt: iso(30), reason: 'auto-archive', tokenCount: 16 },
  { memoryId: 'mem-034', content: 'Trial period extended by 7 days per support ticket #4412', originalStatus: 'active', archivedAt: iso(28), reason: 'manual', tokenCount: 14 },
  { memoryId: 'mem-035', content: 'Old workspace name: "Acme Corp Dev" (renamed to "Acme Engineering")', originalStatus: 'active', archivedAt: iso(25), reason: 'auto-archive', tokenCount: 13 },
  { memoryId: 'mem-036', content: 'Deprecated: user used v1 REST API exclusively (migrated to v2 GraphQL)', originalStatus: 'active', archivedAt: iso(22), reason: 'auto-archive', tokenCount: 17 },
  { memoryId: 'mem-037', content: 'Consolidated from mem-059 + mem-061: Language preferences and timezone settings', originalStatus: 'active', archivedAt: iso(18), reason: 'consolidation', tokenCount: 22 },
  { memoryId: 'mem-039', content: 'Consolidated from mem-010 + mem-011: Integration stack and API preferences', originalStatus: 'active', archivedAt: iso(15), reason: 'consolidation', tokenCount: 24 },
  { memoryId: 'mem-040a', content: 'Previous SSO provider: Okta (migrated to Azure AD)', originalStatus: 'active', archivedAt: iso(12), reason: 'manual', tokenCount: 11 },
  { memoryId: 'mem-041a', content: 'Consolidated from mem-015 + mem-016: UI preferences and query patterns', originalStatus: 'active', archivedAt: iso(8), reason: 'consolidation', tokenCount: 20 },
  { memoryId: 'mem-042a', content: 'User was on Standard plan before upgrading to Enterprise (2025-11-01)', originalStatus: 'active', archivedAt: iso(5), reason: 'consolidation', tokenCount: 15 },
];

// ── Provenance Graph (~150 nodes, ~300 edges) ──────────────────────────

function buildProvenanceGraph(): { nodes: ProvenanceNode[]; edges: ProvenanceEdge[] } {
  const nodes: ProvenanceNode[] = [];
  const edges: ProvenanceEdge[] = [];

  // Layer 1: User interactions (30 nodes)
  const interactionIds: string[] = [];
  for (let i = 0; i < 30; i++) {
    const id = nid();
    interactionIds.push(id);
    nodes.push({
      id,
      type: 'interaction',
      label: `User interaction ${i + 1}`,
      userId: i < 10 ? 'user-1023' : i < 20 ? 'user-8291' : 'user-4517',
      createdAt: iso(365 - i * 12),
    });
  }

  // Layer 2: Memories (60 nodes — mirrors our memory list)
  const memoryNodeIds: string[] = [];
  for (let i = 0; i < 60; i++) {
    const id = nid();
    memoryNodeIds.push(id);
    nodes.push({
      id,
      type: 'memory',
      label: `Memory ${i + 1}`,
      userId: i < 20 ? 'user-1023' : i < 40 ? 'user-8291' : 'user-4517',
      createdAt: iso(350 - i * 5),
    });
  }

  // Layer 3: Summaries / consolidated (20 nodes)
  const summaryIds: string[] = [];
  for (let i = 0; i < 20; i++) {
    const id = nid();
    summaryIds.push(id);
    nodes.push({
      id,
      type: 'summary',
      label: `Consolidated summary ${i + 1}`,
      createdAt: iso(200 - i * 8),
    });
  }

  // Layer 4: Embeddings (25 nodes)
  const embeddingIds: string[] = [];
  for (let i = 0; i < 25; i++) {
    const id = nid();
    embeddingIds.push(id);
    nodes.push({
      id,
      type: 'embedding',
      label: `Embedding vector ${i + 1}`,
      createdAt: iso(300 - i * 10),
    });
  }

  // Layer 5: Responses (18 nodes)
  const responseIds: string[] = [];
  for (let i = 0; i < 18; i++) {
    const id = nid();
    responseIds.push(id);
    nodes.push({
      id,
      type: 'response',
      label: `Agent response ${i + 1}`,
      createdAt: iso(30 - i),
    });
  }

  // Edges: interactions -> memories (creation)
  for (let i = 0; i < 30; i++) {
    const m1 = i * 2;
    const m2 = i * 2 + 1;
    if (m1 < memoryNodeIds.length) {
      edges.push({ id: eid(), source: interactionIds[i], target: memoryNodeIds[m1], type: 'creation', weight: 1.0 });
    }
    if (m2 < memoryNodeIds.length) {
      edges.push({ id: eid(), source: interactionIds[i], target: memoryNodeIds[m2], type: 'creation', weight: 1.0 });
    }
  }

  // Edges: memories -> summaries (derivation)
  for (let i = 0; i < 20; i++) {
    for (let j = 0; j < 3; j++) {
      const mIdx = (i * 3 + j) % memoryNodeIds.length;
      edges.push({ id: eid(), source: memoryNodeIds[mIdx], target: summaryIds[i], type: 'derivation', weight: 0.7 + ((i * 3 + j) % 4) * 0.075 });
    }
  }

  // Edges: memories -> embeddings (derivation)
  for (let i = 0; i < 25; i++) {
    const mIdx = (i * 2) % memoryNodeIds.length;
    edges.push({ id: eid(), source: memoryNodeIds[mIdx], target: embeddingIds[i], type: 'derivation', weight: 1.0 });
    if (i < 15) {
      edges.push({ id: eid(), source: summaryIds[i % summaryIds.length], target: embeddingIds[i], type: 'derivation', weight: 0.8 });
    }
  }

  // Edges: memories/embeddings -> responses (attribution)
  for (let i = 0; i < 18; i++) {
    const count = 3 + (i % 3);
    for (let j = 0; j < count; j++) {
      const mIdx = (i * 4 + j) % memoryNodeIds.length;
      edges.push({ id: eid(), source: memoryNodeIds[mIdx], target: responseIds[i], type: 'attribution', weight: 0.3 + ((i * 4 + j) % 7) * 0.085 });
    }
    const eIdx = i % embeddingIds.length;
    edges.push({ id: eid(), source: embeddingIds[eIdx], target: responseIds[i], type: 'attribution', weight: 0.5 });
  }

  // Cross-links: summaries -> summaries (derivation, for consolidation chains)
  for (let i = 1; i < 10; i++) {
    edges.push({ id: eid(), source: summaryIds[i - 1], target: summaryIds[i], type: 'derivation', weight: 0.6 });
  }

  // Additional memory-to-memory links (contradictions, related)
  const contradictionPairs = [
    [0, 1],   // mem-047 <-> mem-198
    [2, 3],   // mem-012 <-> mem-038
  ];
  for (const [a, b] of contradictionPairs) {
    edges.push({ id: eid(), source: memoryNodeIds[a], target: memoryNodeIds[b], type: 'derivation', weight: 0.1 });
    edges.push({ id: eid(), source: memoryNodeIds[b], target: memoryNodeIds[a], type: 'derivation', weight: 0.1 });
  }

  // Fill to ~300 edges with additional attribution links
  while (edges.length < 300) {
    const srcIdx = Math.floor(edges.length * 7 + 13) % memoryNodeIds.length;
    const tgtIdx = Math.floor(edges.length * 3 + 7) % responseIds.length;
    edges.push({
      id: eid(),
      source: memoryNodeIds[srcIdx],
      target: responseIds[tgtIdx],
      type: 'attribution',
      weight: 0.2 + (edges.length % 5) * 0.1,
    });
  }

  return { nodes, edges };
}

const { nodes: provenanceNodes, edges: provenanceEdges } = buildProvenanceGraph();
export const mockProvenanceNodes: ProvenanceNode[] = provenanceNodes;
export const mockProvenanceEdges: ProvenanceEdge[] = provenanceEdges;

// ── Time Series Data ──────────────────────────────────────────────────

// CHI: baseline ~0.72, dip to ~0.58 around 5 days ago, recovering to ~0.67
const chiHistory = generateTimeSeries30d(0.72, 0.03, 5, 0.14);

// Hallucination rate: baseline ~0.12, spike ~5 days ago correlating with CHI dip
const hallucinationHistory = generateTimeSeries30d(0.12, 0.02, 5, -0.08);

// Token waste: baseline ~0.18, gradual improvement trend
const tokenWasteHistory: TimeSeriesPoint[] = [];
for (let i = 29; i >= 0; i--) {
  const trend = 0.22 - (29 - i) * 0.0013; // slowly improving from 0.22 to ~0.18
  const noise = ((i * 13 + 7) % 9 - 4) * 0.005;
  tokenWasteHistory.push({ timestamp: iso(i), value: Math.max(0, Math.round((trend + noise) * 1000) / 1000) });
}

// Cost: baseline ~$42/day, slight upward trend
const costHistory = generateTimeSeries30d(42, 3);

// Query volume: 24-hour with business-hours pattern
const queryVolumeHistory = generateTimeSeries24h(52, 5);

// ── Dashboard KPIs ─────────────────────────────────────────────────────

const activeMemories = mockMemories.filter(m => m.status === 'active');
const archivedMemories = mockMemories.filter(m => m.status === 'archived');
const avgHealth = activeMemories.reduce((s, m) => s + m.healthScore, 0) / activeMemories.length;
const totalRevenue = activeMemories.reduce((s, m) => s + m.revenuePerDay, 0);
const totalCost = activeMemories.reduce((s, m) => s + m.costPerDay, 0);
const negativeRoiCount = activeMemories.filter(m => m.roi < 0).length;
const highHallucinationTraces = mockQueryTraces.filter(t => t.hallucinationRisk === 'high' || t.hallucinationRisk === 'medium').length;

// Categorize memories by health status
const healthyCount = activeMemories.filter(m => m.healthScore >= 0.7 && m.contradictionsWith.length === 0 && m.driftScore < 0.3).length;
const staleCount = activeMemories.filter(m => m.stalenessScore >= 0.7).length;
const contradictoryCount = activeMemories.filter(m => m.contradictionsWith.length > 0).length;
const driftedCount = activeMemories.filter(m => m.driftScore >= 0.5 && m.contradictionsWith.length === 0).length;

export const mockDashboardKPIs: DashboardKPIs = {
  compositeHealthIndex: Math.round(avgHealth * 100) / 100,
  chiHistory,
  memoryROI: Math.round((totalRevenue / totalCost) * 100) / 100,
  activeMemories: activeMemories.length,
  totalMemories: mockMemories.length,
  attributionConfidence: 0.847,
  hallucinationRate: Math.round((highHallucinationTraces / mockQueryTraces.length) * 100) / 100,
  hallucinationHistory,
  tokenWasteRate: Math.round((negativeRoiCount / activeMemories.length) * 100) / 100,
  tokenWasteHistory,
  gdprStatus: 'pending_deletions',
  pendingDeletions: mockDeletionRequests.filter(d => d.status === 'pending' || d.status === 'processing').length,
  queriesToday: 1247,
  queriesPerSecond: 14.4,
  queryVolumeHistory,
  costToday: 42.18,
  costHistory,
  memoriesByHealth: {
    healthy: healthyCount,
    stale: staleCount,
    contradictory: contradictoryCount,
    drifted: driftedCount,
    archived: archivedMemories.length,
  },
};
