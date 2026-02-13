'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Navigation } from '@/components/Navigation';
import { AnimatedNumber } from '@/components/primitives/AnimatedNumber';

/**
 * CORTEXOS COMPLETE INTELLIGENCE PLATFORM
 *
 * Integrates ALL CortexOS features:
 * - Attribution Engines (Shapley & ContextCite)
 * - GDPR Compliance & Data Deletion
 * - Hallucination Detection
 * - Memory Lifecycle (Hot/Warm/Cold Tiers)
 * - Token Usage Tracking (Input/Output/Context/Cache)
 * - Cross-Referencing & Contradictions
 * - Health Monitoring & Auto-Healing
 */

// Enhanced Status Icon
const StatusIcon = ({ status }: { status: 'active' | 'error' | 'idle' | 'warning' }) => {
  if (status === 'active') {
    return (
      <motion.svg width="14" height="14" viewBox="0 0 14 14" className="inline-block" animate={{ rotate: 360 }} transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}>
        <circle cx="7" cy="7" r="6" fill="none" stroke="#00D9FF" strokeWidth="1.5" strokeDasharray="2 2" />
        <circle cx="7" cy="7" r="2.5" fill="#00D9FF" className="drop-shadow-[0_0_6px_rgba(0,217,255,0.8)]" />
      </motion.svg>
    );
  }
  if (status === 'error') {
    return (
      <motion.svg width="14" height="14" viewBox="0 0 14 14" className="inline-block" animate={{ opacity: [1, 0.4, 1] }} transition={{ duration: 0.8, repeat: Infinity }}>
        <path d="M7 1.5 L12.5 12.5 L1.5 12.5 Z" fill="none" stroke="#FF3A5E" strokeWidth="1.5" />
        <circle cx="7" cy="9" r="1.2" fill="#FF3A5E" className="drop-shadow-[0_0_8px_rgba(255,58,94,0.8)]" />
      </motion.svg>
    );
  }
  if (status === 'warning') {
    return (
      <motion.svg width="14" height="14" viewBox="0 0 14 14" className="inline-block" animate={{ scale: [1, 1.15, 1] }} transition={{ duration: 1.2, repeat: Infinity }}>
        <circle cx="7" cy="7" r="6" fill="none" stroke="#FFB800" strokeWidth="1.5" />
        <line x1="7" y1="4" x2="7" y2="8" stroke="#FFB800" strokeWidth="1.5" />
        <circle cx="7" cy="10" r="0.8" fill="#FFB800" />
      </motion.svg>
    );
  }
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" className="inline-block opacity-30">
      <circle cx="7" cy="7" r="5" fill="none" stroke="#555" strokeWidth="1.5" />
    </svg>
  );
};

// Mini Sparkline
const MiniChart = ({ data, color = '#00D9FF', threshold }: { data: number[], color?: string, threshold?: number }) => {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * 50;
    const y = 16 - ((v - min) / (max - min || 1)) * 16;
    return `${x},${y}`;
  }).join(' ');

  return (
    <svg width="50" height="16" className="inline-block align-middle">
      {threshold && <line x1="0" y1={16 - ((threshold - min) / (max - min || 1)) * 16} x2="50" y2={16 - ((threshold - min) / (max - min || 1)) * 16} stroke="#FF3A5E" strokeWidth="0.5" strokeDasharray="2 1" opacity="0.5" />}
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
};

// Efficiency Badge
const EfficiencyBadge = ({ score }: { score: number }) => {
  const color = score >= 90 ? '#00FF88' : score >= 70 ? '#00D9FF' : score >= 50 ? '#FFB800' : '#FF3A5E';
  const label = score >= 90 ? 'OPTIMAL' : score >= 70 ? 'GOOD' : score >= 50 ? 'FAIR' : 'POOR';
  return (
    <div className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[12px] font-bold" style={{ backgroundColor: `${color}20`, border: `1px solid ${color}40`, color }}>
      {label} {score}
    </div>
  );
};

// Action Menu Component
const ActionMenu = ({ show, onClose }: { show: boolean, onClose: () => void }) => {
  if (!show) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="absolute top-full right-0 mt-1 bg-[#1C1C1E] border border-white/20 rounded shadow-xl z-50 min-w-[160px]"
    >
      <button className="w-full px-3 py-2 text-left text-[13px] text-white/80 hover:bg-white/10 flex items-center gap-2">
        <span>🔍</span> View Details
      </button>
      <button className="w-full px-3 py-2 text-left text-[13px] text-white/80 hover:bg-white/10 flex items-center gap-2">
        <span>📊</span> Attribution Graph
      </button>
      <button className="w-full px-3 py-2 text-left text-[13px] text-white/80 hover:bg-white/10 flex items-center gap-2">
        <span>🔧</span> Optimize Memory
      </button>
      <button className="w-full px-3 py-2 text-left text-[13px] text-white/80 hover:bg-white/10 flex items-center gap-2">
        <span>📝</span> View Logs
      </button>
      <div className="border-t border-white/10 my-1" />
      <button className="w-full px-3 py-2 text-left text-[13px] text-white/80 hover:bg-white/10 flex items-center gap-2">
        <span>🔄</span> Restart Agent
      </button>
      <button className="w-full px-3 py-2 text-left text-[13px] text-[#FF3A5E] hover:bg-[#FF3A5E]/10 flex items-center gap-2">
        <span>⚠️</span> Force Archive
      </button>
      <button className="w-full px-3 py-2 text-left text-[13px] text-[#FF3A5E] hover:bg-[#FF3A5E]/10 flex items-center gap-2">
        <span>🗑️</span> Delete (GDPR)
      </button>
    </motion.div>
  );
};

export default function CortexHUD() {
  const [time, setTime] = React.useState(new Date());
  const [commandInput, setCommandInput] = React.useState('');
  const [selectedAgentId, setSelectedAgentId] = React.useState<string | null>(null);
  const [logStream, setLogStream] = React.useState<Array<{time: string, level: string, msg: string}>>([]);
  const [showActionMenu, setShowActionMenu] = React.useState<string | null>(null);

  const generateHistory = (len: number) => Array.from({ length: len }, () => Math.random() * 100);

  // Enhanced agents with ALL CortexOS metrics
  const [agents, setAgents] = React.useState([
    { id: '001', agent: 'legal-retrieval', q: 1247, lat: 8.2, err: 2, cost: 0.0023, acc: 98.2, mem: 72, cpu: 45, status: 'active' as const, sla: 95, efficiency: 92, costPerQ: 0.0018,
      attribution: { method: 'Shapley', confidence: 0.89, memoryCount: 12 },
      tokens: { input: 1247000, output: 843000, context: 234000, cached: 156000 },
      hallucination: 2.3, contradictions: 1,
      memoryTier: { hot: 4200, warm: 8300, cold: 12400 },
      gdpr: { pending: 2, completed: 7 },
      qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
    },
    { id: '002', agent: 'finance-analysis', q: 892, lat: 12.4, err: 0, cost: 0.0031, acc: 99.1, mem: 45, cpu: 38, status: 'active' as const, sla: 98, efficiency: 88, costPerQ: 0.0035,
      attribution: { method: 'ContextCite', confidence: 0.94, memoryCount: 8 },
      tokens: { input: 892000, output: 634000, context: 178000, cached: 98000 },
      hallucination: 1.1, contradictions: 0,
      memoryTier: { hot: 3100, warm: 5200, cold: 8900 },
      gdpr: { pending: 0, completed: 3 },
      qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
    },
    { id: '003', agent: 'hr-compliance', q: 634, lat: 6.1, err: 1, cost: 0.0019, acc: 97.8, mem: 38, cpu: 22, status: 'idle' as const, sla: 99, efficiency: 94, costPerQ: 0.003,
      attribution: { method: 'Shapley', confidence: 0.92, memoryCount: 6 },
      tokens: { input: 634000, output: 421000, context: 112000, cached: 67000 },
      hallucination: 0.8, contradictions: 0,
      memoryTier: { hot: 2300, warm: 3900, cold: 6700 },
      gdpr: { pending: 5, completed: 12 },
      qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
    },
    { id: '004', agent: 'sales-insights', q: 421, lat: 15.8, err: 5, cost: 0.0042, acc: 94.3, mem: 81, cpu: 67, status: 'error' as const, sla: 87, efficiency: 45, costPerQ: 0.01,
      attribution: { method: 'ContextCite', confidence: 0.67, memoryCount: 15 },
      tokens: { input: 421000, output: 289000, context: 89000, cached: 34000 },
      hallucination: 8.7, contradictions: 4,
      memoryTier: { hot: 5600, warm: 12300, cold: 18900 },
      gdpr: { pending: 1, completed: 2 },
      qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
    },
    // ... Continue with remaining 16 agents (keeping code concise for token limit)
    { id: '020', agent: 'cache-manager', q: 1890, lat: 2.1, err: 0, cost: 0.0009, acc: 99.9, mem: 28, cpu: 14, status: 'active' as const, sla: 100, efficiency: 99, costPerQ: 0.0005,
      attribution: { method: 'Exact Shapley', confidence: 1.0, memoryCount: 3 },
      tokens: { input: 1890000, output: 1234000, context: 456000, cached: 389000 },
      hallucination: 0.1, contradictions: 0,
      memoryTier: { hot: 8900, warm: 4200, cold: 2100 },
      gdpr: { pending: 0, completed: 0 },
      qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
    },
  ].concat(Array.from({ length: 15 }, (_, i) => ({
    id: String(i + 5).padStart(3, '0'),
    agent: ['support-routing', 'marketing-content', 'product-research', 'risk-assessment', 'compliance-audit', 'data-pipeline', 'ml-inference', 'analytics-engine', 'search-indexer', 'recommendation', 'fraud-detection', 'sentiment-analysis', 'translation-service', 'image-recognition', 'voice-synthesis'][i],
    q: Math.floor(Math.random() * 1000) + 100,
    lat: Math.random() * 20 + 2,
    err: Math.floor(Math.random() * 10),
    cost: Math.random() * 0.005 + 0.001,
    acc: Math.random() * 10 + 90,
    mem: Math.floor(Math.random() * 60) + 20,
    cpu: Math.floor(Math.random() * 60) + 15,
    status: ['active', 'warning', 'idle'][Math.floor(Math.random() * 3)] as const,
    sla: Math.floor(Math.random() * 20) + 80,
    efficiency: Math.floor(Math.random() * 50) + 50,
    costPerQ: Math.random() * 0.01 + 0.001,
    attribution: { method: ['Shapley', 'ContextCite', 'Exact Shapley'][Math.floor(Math.random() * 3)], confidence: Math.random() * 0.3 + 0.7, memoryCount: Math.floor(Math.random() * 15) + 3 },
    tokens: { input: Math.floor(Math.random() * 1000000) + 100000, output: Math.floor(Math.random() * 700000) + 70000, context: Math.floor(Math.random() * 300000) + 50000, cached: Math.floor(Math.random() * 200000) + 20000 },
    hallucination: Math.random() * 10,
    contradictions: Math.floor(Math.random() * 5),
    memoryTier: { hot: Math.floor(Math.random() * 8000) + 1000, warm: Math.floor(Math.random() * 10000) + 2000, cold: Math.floor(Math.random() * 15000) + 3000 },
    gdpr: { pending: Math.floor(Math.random() * 10), completed: Math.floor(Math.random() * 20) },
    qHist: generateHistory(60), latHist: generateHistory(60), memHist: generateHistory(60)
  }))));

  // Real-time updates - Enhanced for YC demo
  React.useEffect(() => {
    const interval = setInterval(() => {
      setTime(new Date());
      setAgents(prev => prev.map(a => {
        // Simulate "processing bursts" for active agents
        const isProcessing = a.status === 'active' && Math.random() > 0.7;
        const queryIncrement = isProcessing ? Math.floor(Math.random() * 15) + 5 : Math.floor(Math.random() * 3);

        return {
          ...a,
          q: a.q + queryIncrement,
          lat: Math.max(2, a.lat + (Math.random() - 0.5) * 2),
          mem: Math.max(10, Math.min(95, a.mem + (Math.random() - 0.5) * 5)),
          cpu: Math.max(10, Math.min(95, a.cpu + (Math.random() - 0.5) * 5)),
          hallucination: Math.max(0, a.hallucination + (Math.random() - 0.5) * 0.5),
          tokens: {
            ...a.tokens,
            input: a.tokens.input + (queryIncrement * 800),
            output: a.tokens.output + (queryIncrement * 550),
            cached: a.tokens.cached + (queryIncrement * 100),
          },
          qHist: [...a.qHist.slice(1), a.q],
          latHist: [...a.latHist.slice(1), a.lat],
          memHist: [...a.memHist.slice(1), a.mem],
          isProcessing, // Add processing state for visual indicator
        };
      }));

      if (Math.random() > 0.7) {
        const levels = ['INFO', 'WARN', 'ERRO'];
        const msgs = ['Attribution computed (Shapley)', 'Memory archived to cold tier', 'GDPR deletion completed', 'Hallucination detected', 'Contradiction resolved', 'Token cache hit'];
        setLogStream(prev => [
          { time: new Date().toISOString().slice(11, 23), level: levels[Math.floor(Math.random() * levels.length)], msg: msgs[Math.floor(Math.random() * msgs.length)] },
          ...prev.slice(0, 49)
        ]);
      }
    }, 100);
    return () => clearInterval(interval);
  }, []);

  const total = {
    queries: agents.reduce((s, a) => s + a.q, 0),
    errors: agents.reduce((s, a) => s + a.err, 0),
    cost: agents.reduce((s, a) => s + a.cost, 0),
    avgLat: agents.reduce((s, a) => s + a.lat, 0) / agents.length,
    avgAcc: agents.reduce((s, a) => s + a.acc, 0) / agents.length,
    avgMem: agents.reduce((s, a) => s + a.mem, 0) / agents.length,
    avgCpu: agents.reduce((s, a) => s + a.cpu, 0) / agents.length,
    avgSla: agents.reduce((s, a) => s + a.sla, 0) / agents.length,
    avgEfficiency: agents.reduce((s, a) => s + a.efficiency, 0) / agents.length,
    avgHallucination: agents.reduce((s, a) => s + a.hallucination, 0) / agents.length,
    totalContradictions: agents.reduce((s, a) => s + a.contradictions, 0),
    totalTokens: agents.reduce((s, a) => s + a.tokens.input + a.tokens.output, 0),
    cachedTokens: agents.reduce((s, a) => s + a.tokens.cached, 0),
    totalMemories: agents.reduce((s, a) => s + a.memoryTier.hot + a.memoryTier.warm + a.memoryTier.cold, 0),
    gdprPending: agents.reduce((s, a) => s + a.gdpr.pending, 0),
  };

  const costPerHour = total.cost * 36;
  const costPerQuery = total.cost / total.queries;
  const projectedDailyCost = costPerHour * 24;
  const errorRate = (total.errors / total.queries) * 100;
  const slaBreaches = agents.filter(a => a.sla < 95).length;
  const inefficientAgents = agents.filter(a => a.efficiency < 70);
  const highHallucinationAgents = agents.filter(a => a.hallucination > 5);
  const cacheHitRate = (total.cachedTokens / total.totalTokens) * 100;

  const selectedAgent = agents.find(a => a.id === selectedAgentId);

  return (
    <div className="relative min-h-screen bg-[#0A0A0A] text-white/70 font-mono overflow-hidden">
      <Navigation />

      {/* CRT Atmosphere */}
      <div className="pointer-events-none fixed inset-0 z-[60]">
        {/* Vignette */}
        <div className="absolute inset-0" style={{
          background: 'radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.4) 100%)'
        }} />
        {/* Scanlines */}
        <div className="absolute inset-0 opacity-[0.02]" style={{
          background: 'repeating-linear-gradient(0deg, transparent 0px, rgba(255,255,255,0.03) 1px, transparent 2px)'
        }} />
      </div>

      {/* Header */}
      <div className="border-b border-white/10 bg-black/90 backdrop-blur-sm px-4 py-2 flex justify-between items-center sticky top-0 z-30">
        <div className="flex items-center gap-6">
          <span className="text-[13px] font-bold text-white">CORTEX INTELLIGENCE</span>
          <span className="text-[14px] text-[#00D9FF] tabular-nums">{time.toISOString().slice(11, 19)}</span>
          <div className="flex items-center gap-3 text-[13px]">
            <span className="text-white/90"><span className="text-white/80">$/HR</span> <span className="text-white font-bold tabular-nums">${costPerHour.toFixed(2)}</span></span>
            <span className="text-white/90"><span className="text-white/80">TOKENS</span> <span className="text-white font-bold tabular-nums">{(total.totalTokens / 1000000).toFixed(1)}M</span></span>
            <span className="text-white/90"><span className="text-white/80">CACHE</span> <span className="text-white font-bold tabular-nums">{cacheHitRate.toFixed(0)}%</span></span>
            <span className="text-white/90"><span className="text-white/80">HALL</span> <span className={`font-bold tabular-nums ${total.avgHallucination < 3 ? 'text-white' : 'text-white'}`} style={total.avgHallucination >= 5 ? { textShadow: '0 0 10px rgba(255,184,0,0.8)' } : {}}>{total.avgHallucination.toFixed(1)}%</span></span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[12px] text-white/85">REAL-TIME</span>
          <div className="w-2 h-2 rounded-full bg-[#00FF88] animate-pulse shadow-[0_0_8px_rgba(0,255,136,0.6)]" />
        </div>
      </div>

      {/* Main Grid - Zero-Entropy Layout */}
      <div className="grid gap-0 min-h-[calc(100vh-90px)]" style={{ gridTemplateColumns: selectedAgent ? '320px 1fr 340px 300px' : '320px 1fr 340px' }}>

        {/* LEFT COLUMN */}
        <div className="flex flex-col gap-0 border-r border-white/10">

          {/* Executive Summary */}
          <motion.div
            className="bg-[#0A0A0A] border-b border-white/10 p-3 relative overflow-hidden rounded-none"
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.4 }}
          >
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-[0.02]" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, #00D9FF 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }} />

            <div className="flex items-center justify-between mb-3 relative z-10">
              <span className="text-[14px] font-bold text-white/90 tracking-wide">EXECUTIVE SUMMARY</span>
              <motion.div
                className="text-[12px] text-[#00D9FF] font-bold px-2 py-0.5 bg-[#00D9FF]/10 rounded border border-[#00D9FF]/20"
                animate={{ opacity: [0.7, 1, 0.7] }}
                transition={{ duration: 2, repeat: Infinity }}
              >
                LIVE
              </motion.div>
            </div>

            <div className="space-y-0 relative z-10">
              {/* Token Economics */}
              <motion.div
                className="bg-[#0A0A0A] border-b border-white/10 p-2.5 hover:bg-white/[0.02] transition-colors"
                whileHover={{ backgroundColor: 'rgba(255,255,255,0.02)' }}
                transition={{ duration: 0.15 }}
              >
                <div className="text-[12px] text-white/85 mb-1.5 uppercase tracking-wider">Token Usage (24H)</div>
                <div className="flex items-baseline gap-2 mb-2">
                  <AnimatedNumber value={total.totalTokens / 1000000} decimals={2} suffix="M" fontSize="20px" className="text-[#00D9FF] font-bold" />
                  <span className="text-[13px] text-white/80">tokens</span>
                </div>
                <div className="flex items-center gap-2 text-[12px]">
                  <span className="text-white/90">Cache Hit:</span>
                  <div className="flex-1 h-1.5 bg-black/30 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-[#00FF88] to-[#00D9FF] rounded-full"
                      initial={{ width: 0 }}
                      animate={{ width: `${cacheHitRate}%` }}
                      transition={{ duration: 1, ease: "easeOut" }}
                    />
                  </div>
                  <span className="text-[#00FF88] font-bold tabular-nums w-10 text-right">{cacheHitRate.toFixed(0)}%</span>
                </div>
              </motion.div>

              {/* Hallucination Risk */}
              <motion.div
                className="bg-[#0A0A0A] border-b border-white/10 p-2.5 hover:bg-white/[0.02] transition-colors"
                whileHover={{ backgroundColor: 'rgba(255,255,255,0.02)' }}
                transition={{ duration: 0.15 }}
              >
                <div className="text-[12px] text-white/80 mb-1.5 uppercase tracking-wider">Hallucination Risk</div>
                <div className="flex items-center justify-between">
                  <div className="flex items-baseline gap-2">
                    <motion.div
                      className="text-[20px] font-bold tabular-nums text-white"
                      style={total.avgHallucination > 5 ? { textShadow: '0 0 12px rgba(255,184,0,0.9)' } : {}}
                      animate={total.avgHallucination > 5 ? {
                        textShadow: ['0 0 12px rgba(255,184,0,0.9)', '0 0 20px rgba(255,184,0,1)', '0 0 12px rgba(255,184,0,0.9)']
                      } : {}}
                      transition={{ duration: 0.8, repeat: total.avgHallucination > 5 ? Infinity : 0 }}
                    >
                      {total.avgHallucination.toFixed(1)}%
                    </motion.div>
                  </div>
                  <EfficiencyBadge score={total.avgHallucination < 3 ? 90 : total.avgHallucination < 5 ? 70 : 40} />
                </div>
                <div className="text-[12px] text-white/80 mt-1.5">{highHallucinationAgents.length} agents above threshold</div>
              </motion.div>

              {/* GDPR Compliance */}
              <motion.div
                className="bg-[#0A0A0A] border-b border-white/10 p-2.5 hover:bg-white/[0.02] transition-colors"
                whileHover={{ backgroundColor: 'rgba(255,255,255,0.02)' }}
                transition={{ duration: 0.15 }}
              >
                <div className="text-[12px] text-white/80 mb-1.5 uppercase tracking-wider">GDPR Deletions</div>
                <div className="flex items-baseline gap-2 mb-1">
                  <AnimatedNumber value={total.gdprPending} decimals={0} fontSize="20px" className="text-white font-bold tabular-nums" />
                  <span className="text-[13px] text-white/80">pending</span>
                </div>
                <div className="flex items-center gap-1.5 text-[12px] text-white/80">
                  <motion.div
                    className="w-1 h-1 bg-[#FFB800]"
                    animate={{ opacity: [0.3, 1, 0.3] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                  />
                  <span>30-day compliance window</span>
                </div>
              </motion.div>

              {/* Key Actions */}
              <div className="space-y-0">
                <div className="text-[13px] font-bold text-white/80 mb-2 uppercase tracking-wider">RECOMMENDED ACTIONS</div>

                {highHallucinationAgents.length > 0 && (
                  <motion.div
                    className="bg-[#0A0A0A] border-b border-[#FF3A5E]/30 p-2 text-[13px]"
                    animate={{ borderColor: ['rgba(255,58,94,0.3)', 'rgba(255,58,94,0.6)', 'rgba(255,58,94,0.3)'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <StatusIcon status="error" />
                      <span className="text-white font-bold">{highHallucinationAgents.length} HIGH HALLUCINATION</span>
                    </div>
                    <div className="text-white/80 text-[12px]">Review memory quality & contradictions</div>
                  </motion.div>
                )}

                {total.totalContradictions > 10 && (
                  <motion.div
                    className="bg-[#0A0A0A] border-b border-[#FFB800]/30 p-2 text-[13px]"
                    animate={{ borderColor: ['rgba(255,184,0,0.3)', 'rgba(255,184,0,0.6)', 'rgba(255,184,0,0.3)'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <StatusIcon status="warning" />
                      <span className="text-white font-bold">{total.totalContradictions} CONTRADICTIONS</span>
                    </div>
                    <div className="text-white/80 text-[12px]">Cross-reference & merge memories</div>
                  </motion.div>
                )}

                {total.gdprPending > 0 && (
                  <motion.div
                    className="bg-[#0A0A0A] border-b border-[#00D9FF]/30 p-2 text-[13px]"
                    animate={{ borderColor: ['rgba(0,217,255,0.3)', 'rgba(0,217,255,0.6)', 'rgba(0,217,255,0.3)'] }}
                    transition={{ duration: 2, repeat: Infinity }}
                  >
                    <div className="flex items-center gap-1.5 mb-1">
                      <StatusIcon status="active" />
                      <span className="text-white font-bold">GDPR: {total.gdprPending} PENDING</span>
                    </div>
                    <div className="text-white/80 text-[12px]">Complete before 30-day deadline</div>
                  </motion.div>
                )}
              </div>
            </div>
          </motion.div>

          {/* Attribution Engines */}
          <div className="bg-[#0A0A0A] border-b border-white/10">
            <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02]">
              <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">ATTRIBUTION ENGINES</span>
            </div>
            <div className="p-2 space-y-0">
              {[
                { method: 'Shapley Values', agents: agents.filter(a => a.attribution.method.includes('Shapley')).length, avgConf: agents.filter(a => a.attribution.method.includes('Shapley')).reduce((s, a) => s + a.attribution.confidence, 0) / agents.filter(a => a.attribution.method.includes('Shapley')).length, color: '#00D9FF' },
                { method: 'ContextCite', agents: agents.filter(a => a.attribution.method === 'ContextCite').length, avgConf: agents.filter(a => a.attribution.method === 'ContextCite').reduce((s, a) => s + a.attribution.confidence, 0) / agents.filter(a => a.attribution.method === 'ContextCite').length, color: '#00FF88' },
              ].map((engine, i) => (
                <div key={i} className="bg-[#0A0A0A] border-b border-white/10 p-2">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[13px] text-white/80 font-bold uppercase">{engine.method}</span>
                    <span className="text-[12px] text-white/80">{engine.agents} agents</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[12px] text-white/80">LDS:</span>
                    <div className="flex-1 h-1 bg-white/5">
                      <motion.div
                        className="h-full"
                        style={{ background: engine.color }}
                        initial={{ width: 0 }}
                        animate={{ width: `${engine.avgConf * 100}%` }}
                        transition={{ duration: 1, ease: "easeOut" }}
                      />
                    </div>
                    <span className="text-[13px] font-bold tabular-nums text-white">{(engine.avgConf * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Memory Lifecycle */}
          <div className="bg-[#0A0A0A] border-b border-white/10 flex-1">
            <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02]">
              <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">MEMORY LIFECYCLE</span>
            </div>
            <div className="p-2 space-y-0">
              {[
                { tier: 'HOT', count: agents.reduce((s, a) => s + a.memoryTier.hot, 0), color: '#FF3A5E', pct: (agents.reduce((s, a) => s + a.memoryTier.hot, 0) / total.totalMemories) * 100 },
                { tier: 'WARM', count: agents.reduce((s, a) => s + a.memoryTier.warm, 0), color: '#FFB800', pct: (agents.reduce((s, a) => s + a.memoryTier.warm, 0) / total.totalMemories) * 100 },
                { tier: 'COLD', count: agents.reduce((s, a) => s + a.memoryTier.cold, 0), color: '#00D9FF', pct: (agents.reduce((s, a) => s + a.memoryTier.cold, 0) / total.totalMemories) * 100 },
              ].map((tier, i) => (
                <div key={i} className="border-b border-white/10 p-2">
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-white/80 font-bold">{tier.tier}</span>
                    <span className="text-white tabular-nums font-bold">{(tier.count / 1000).toFixed(1)}K ({tier.pct.toFixed(0)}%)</span>
                  </div>
                  <div className="h-1 bg-white/5">
                    <motion.div
                      className="h-full"
                      style={{ background: tier.color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${tier.pct}%` }}
                      transition={{ duration: 0.8, ease: "easeOut" }}
                    />
                  </div>
                </div>
              ))}
              <div className="text-[12px] text-white/80 mt-2 text-center font-bold tabular-nums">
                TOTAL: {(total.totalMemories / 1000).toFixed(1)}K MEMORIES
              </div>
            </div>
          </div>
        </div>

        {/* CENTER COLUMN - Agent Table */}
        <div className="bg-[#0A0A0A] border-r border-white/10 overflow-hidden flex flex-col">
          <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02] backdrop-blur-md sticky top-0 z-20 flex justify-between items-center">
            <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">AGENT PERFORMANCE MONITOR</span>
            <span className="text-[12px] text-white/80 tabular-nums">20 AGENTS • 100ms REFRESH</span>
          </div>

          <div className="overflow-auto flex-1">
            <table className="w-full border-collapse text-[13px]">
              <thead className="sticky top-0 bg-[#0A0A0A]/95 backdrop-blur-md z-10">
                <tr className="border-b border-white/30">
                  <th className="text-left text-white/90 font-bold px-2 py-2 text-[13px] uppercase tracking-wider">AGENT</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">Q</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">LAT</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">ATR</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">TOK</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">HALL</th>
                  <th className="text-right text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">EFF</th>
                  <th className="text-left text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">TREND</th>
                  <th className="text-center text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">ST</th>
                  <th className="text-center text-white/90 font-bold px-1.5 py-2 text-[13px] uppercase tracking-wider">ACT</th>
                </tr>
              </thead>
              <tbody>
                {agents.map((a, i) => (
                  <motion.tr
                    key={a.id}
                    onClick={() => setSelectedAgentId(selectedAgentId === a.id ? null : a.id)}
                    className={`border-b border-white/5 cursor-pointer ${selectedAgentId === a.id ? 'bg-[#00D9FF]/10' : i % 2 === 0 ? 'bg-[#0A0A0A]' : 'bg-white/[0.02]'}`}
                    whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.08)', transition: { duration: 0.15 } }}
                    whileTap={{ scale: 0.998 }}
                  >
                    <td className="px-2 py-1.5">
                      <div className="text-[#00D9FF] text-[13px]">{a.agent}</div>
                      <div className="text-[8px] text-white/85">{a.attribution.method}</div>
                    </td>
                    <td className="text-right text-white tabular-nums px-1.5 py-1.5 text-[14px] font-bold">{a.q}</td>
                    <td className="text-right tabular-nums px-1.5 py-1.5 text-[14px] font-bold text-white" style={a.lat > 50 ? { textShadow: '0 0 10px rgba(255,58,94,0.8)' } : {}}>
                      {a.lat.toFixed(1)}
                    </td>
                    <td className="text-right tabular-nums px-1.5 py-1.5 text-[13px]" style={{ color: a.attribution.confidence > 0.85 ? '#00FF88' : a.attribution.confidence > 0.7 ? '#FFB800' : '#FF3A5E' }}>
                      {(a.attribution.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="text-right tabular-nums px-1.5 py-1.5 text-[13px] text-white/70">
                      {((a.tokens.input + a.tokens.output) / 1000).toFixed(0)}K
                    </td>
                    <td className="text-right tabular-nums px-1.5 py-1.5 text-[14px] font-bold text-white" style={a.hallucination > 5 ? { textShadow: '0 0 10px rgba(255,184,0,0.8)' } : {}}>
                      {a.hallucination.toFixed(1)}
                    </td>
                    <td className="text-right px-1.5 py-1.5 text-[12px]">
                      <EfficiencyBadge score={a.efficiency} />
                    </td>
                    <td className="px-1.5 py-1.5">
                      <MiniChart data={a.latHist.slice(-15)} color={a.lat > 15 ? '#FF3A5E' : '#00FF88'} threshold={15} />
                    </td>
                    <td className="text-center px-1.5 py-1.5">
                      <StatusIcon status={a.status} />
                    </td>
                    <td className="text-center px-1.5 py-1.5 relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setShowActionMenu(showActionMenu === a.id ? null : a.id);
                        }}
                        className="text-white/60 hover:text-white text-[12px]"
                      >
                        ⋮
                      </button>
                      <AnimatePresence>
                        {showActionMenu === a.id && (
                          <ActionMenu show={true} onClose={() => setShowActionMenu(null)} />
                        )}
                      </AnimatePresence>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* RIGHT COLUMN - Analytics */}
        <div className="flex flex-col gap-px bg-[#0F0F0F]">

          {/* Contradictions & Cross-Refs */}
          <div className="bg-[#0A0A0A] border border-white/10">
            <div className="border-b border-white/10 px-3 py-2 bg-white/5">
              <span className="text-[14px] font-bold text-white/70">CONTRADICTIONS</span>
            </div>
            <div className="p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-white/90">Total Detected</span>
                <span className="text-[16px] font-bold text-[#FF3A5E] tabular-nums">{total.totalContradictions}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-white/90">Avg per Agent</span>
                <span className="text-[14px] font-bold text-[#FFB800] tabular-nums">{(total.totalContradictions / agents.length).toFixed(1)}</span>
              </div>
              <div className="text-[12px] text-white/85 mt-2">
                Cross-reference {agents.filter(a => a.contradictions > 0).length} agents for memory conflicts
              </div>
            </div>
          </div>

          {/* Token Analytics */}
          <div className="bg-[#0A0A0A] border-b border-white/10">
            <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02]">
              <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">TOKEN ANALYTICS</span>
            </div>
            <div className="p-2 space-y-0">
              {[
                { label: 'Input', value: agents.reduce((s, a) => s + a.tokens.input, 0), color: '#00D9FF' },
                { label: 'Output', value: agents.reduce((s, a) => s + a.tokens.output, 0), color: '#00FF88' },
                { label: 'Context', value: agents.reduce((s, a) => s + a.tokens.context, 0), color: '#FFB800' },
                { label: 'Cached', value: agents.reduce((s, a) => s + a.tokens.cached, 0), color: '#FF3A5E' },
              ].map((tok, i) => (
                <div key={i} className="border-b border-white/10 p-2">
                  <div className="flex justify-between text-[12px] mb-1">
                    <span className="text-white/80 font-bold uppercase">{tok.label}</span>
                    <span className="text-white tabular-nums font-bold">{(tok.value / 1000000).toFixed(2)}M</span>
                  </div>
                  <div className="h-1 bg-white/5">
                    <motion.div
                      className="h-full"
                      style={{ background: tok.color }}
                      initial={{ width: 0 }}
                      animate={{ width: `${(tok.value / total.totalTokens) * 100}%` }}
                      transition={{ duration: 0.8, ease: "easeOut" }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Live Log */}
          <div className="bg-[#0A0A0A] border-b border-white/10 flex-1 flex flex-col">
            <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02]">
              <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">LIVE TELEMETRY</span>
            </div>
            <div className="overflow-auto flex-1 p-2 text-[12px] space-y-0 font-mono">
              {logStream.map((log, i) => (
                <div key={i} className="border-b border-white/5 py-1">
                  <span className="text-white/80 tabular-nums">{log.time}</span>
                  {' '}
                  <span className="font-bold text-white" style={log.level === 'ERRO' ? { textShadow: '0 0 8px rgba(255,58,94,0.8)' } : log.level === 'WARN' ? { textShadow: '0 0 8px rgba(255,184,0,0.8)' } : {}}>
                    {log.level}
                  </span>
                  {' '}
                  <span className="text-white/60">{log.msg}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* FOURTH COLUMN - Agent Details */}
        {selectedAgent && (
          <motion.div
            className="flex flex-col gap-0 bg-[#0A0A0A]"
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
          >
            <div className="bg-[#0A0A0A] border-l border-white/10">
              <div className="border-b border-white/10 px-3 py-2 bg-white/[0.02] flex justify-between items-center">
                <span className="text-[14px] font-bold text-white/80 uppercase tracking-wider">{selectedAgent.agent.toUpperCase()}</span>
                <button onClick={() => setSelectedAgentId(null)} className="text-white/80 hover:text-white text-[14px]">✕</button>
              </div>
              <div className="p-3 space-y-0 text-[13px]">
                {/* Attribution Details */}
                <div className="bg-[#0A0A0A] border-b border-white/10 p-2">
                  <div className="text-white/80 mb-1 text-[12px] font-bold uppercase tracking-wider">ATTRIBUTION ENGINE</div>
                  <div className="font-bold text-white">{selectedAgent.attribution.method}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-[12px] text-white/80">LDS Confidence:</span>
                    <span className="font-bold tabular-nums text-white">
                      {(selectedAgent.attribution.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div className="text-[12px] text-white/80 mt-1">{selectedAgent.attribution.memoryCount} memories analyzed</div>
                </div>

                {/* Token Breakdown */}
                <div className="bg-[#0A0A0A] border-b border-white/10 p-2">
                  <div className="text-white/80 mb-1 text-[12px] font-bold uppercase tracking-wider">TOKEN USAGE</div>
                  <div className="space-y-1">
                    {[
                      { label: 'Input', value: selectedAgent.tokens.input },
                      { label: 'Output', value: selectedAgent.tokens.output },
                      { label: 'Context', value: selectedAgent.tokens.context },
                      { label: 'Cached', value: selectedAgent.tokens.cached, highlight: true },
                    ].map((t, i) => (
                      <div key={i} className="flex justify-between text-[12px]">
                        <span className="text-white/80 uppercase">{t.label}</span>
                        <span className="font-bold tabular-nums text-white">
                          {(t.value / 1000).toFixed(0)}K
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Hallucination & Contradictions */}
                <div className="bg-[#0A0A0A] border-b border-white/10 p-2">
                  <div className="text-white/80 mb-1 text-[12px] font-bold uppercase tracking-wider">QUALITY METRICS</div>
                  <div className="space-y-1">
                    <div className="flex justify-between">
                      <span className="text-white/80 text-[12px] uppercase">Hallucination</span>
                      <span className="font-bold tabular-nums text-white" style={selectedAgent.hallucination > 5 ? { textShadow: '0 0 8px rgba(255,58,94,0.8)' } : {}}>
                        {selectedAgent.hallucination.toFixed(1)}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80 text-[12px] uppercase">Contradictions</span>
                      <span className="font-bold tabular-nums text-white" style={selectedAgent.contradictions > 0 ? { textShadow: '0 0 8px rgba(255,58,94,0.8)' } : {}}>
                        {selectedAgent.contradictions}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Memory Tiers */}
                <div className="bg-white/5 rounded p-2">
                  <div className="text-white/90 mb-1 text-[12px]">MEMORY TIERS</div>
                  {[
                    { tier: 'Hot', count: selectedAgent.memoryTier.hot, color: '#FF3A5E' },
                    { tier: 'Warm', count: selectedAgent.memoryTier.warm, color: '#FFB800' },
                    { tier: 'Cold', count: selectedAgent.memoryTier.cold, color: '#00D9FF' },
                  ].map((m, i) => (
                    <div key={i} className="flex justify-between text-[12px] mb-0.5">
                      <span className="text-white/90">{m.tier}</span>
                      <span className="font-bold tabular-nums" style={{ color: m.color }}>{m.count}</span>
                    </div>
                  ))}
                </div>

                {/* GDPR Status */}
                <div className={`rounded p-2 ${selectedAgent.gdpr.pending > 0 ? 'bg-[#FFB800]/10 border border-[#FFB800]/30' : 'bg-white/5'}`}>
                  <div className="text-white/90 mb-1 text-[12px]">GDPR COMPLIANCE</div>
                  <div className="flex justify-between text-[12px]">
                    <span className="text-white/90">Pending Deletions</span>
                    <span className={`font-bold tabular-nums ${selectedAgent.gdpr.pending > 0 ? 'text-[#FFB800]' : 'text-[#00FF88]'}`}>
                      {selectedAgent.gdpr.pending}
                    </span>
                  </div>
                  <div className="flex justify-between text-[12px] mt-0.5">
                    <span className="text-white/90">Completed (30d)</span>
                    <span className="font-bold tabular-nums text-white/70">{selectedAgent.gdpr.completed}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Latency Graph */}
            <div className="bg-[#0A0A0A] border border-white/10">
              <div className="border-b border-white/10 px-3 py-2 bg-white/5">
                <span className="text-[14px] font-bold text-white/70">LATENCY (60s)</span>
              </div>
              <div className="p-3">
                <svg width="100%" height="80">
                  <polyline
                    points={selectedAgent.latHist.map((v, i) => `${(i / 60) * 260},${80 - v * 3}`).join(' ')}
                    fill="none"
                    stroke={selectedAgent.lat > 15 ? '#FF3A5E' : '#00FF88'}
                    strokeWidth="2"
                    className="drop-shadow-[0_0_4px_rgba(0,255,136,0.3)]"
                  />
                  <line x1="0" y1="40" x2="260" y2="40" stroke="#FFB800" strokeWidth="1" strokeDasharray="4 2" opacity="0.3" />
                </svg>
              </div>
            </div>

            {/* Enhanced Actions */}
            <div className="bg-[#0A0A0A] border border-white/10 flex-1">
              <div className="border-b border-white/10 px-3 py-2 bg-white/5">
                <span className="text-[14px] font-bold text-white/70">ACTIONS</span>
              </div>
              <div className="p-2 space-y-1.5">
                <motion.button className="w-full py-1.5 px-2 bg-white/5 border border-white/20 text-[#00D9FF] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.1)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>🎯</span> View Attribution Graph
                </motion.button>
                <motion.button className="w-full py-1.5 px-2 bg-white/5 border border-white/20 text-[#00D9FF] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.1)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>🔗</span> Cross-Reference Memories
                </motion.button>
                <motion.button className="w-full py-1.5 px-2 bg-white/5 border border-white/20 text-[#00D9FF] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.1)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>⚡</span> Optimize Tier Migration
                </motion.button>
                <motion.button className="w-full py-1.5 px-2 bg-white/5 border border-white/20 text-[#00D9FF] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.1)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>📊</span> Export Token Report
                </motion.button>
                <motion.button className="w-full py-1.5 px-2 bg-white/5 border border-white/20 text-[#00D9FF] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(0, 217, 255, 0.1)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>🔄</span> Restart Agent
                </motion.button>
                <motion.button className="w-full py-1.5 px-2 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] text-[13px] font-mono rounded text-left flex items-center gap-2" whileHover={{ backgroundColor: 'rgba(255, 58, 94, 0.15)', scale: 1.01 }} whileTap={{ scale: 0.99 }}>
                  <span>🗑️</span> GDPR Delete Request
                </motion.button>
              </div>
            </div>
          </motion.div>
        )}
      </div>

      {/* Command Terminal */}
      <div className="border-t border-white/10 bg-black/95 backdrop-blur-sm fixed bottom-0 left-0 right-0 z-30">
        <div className="px-4 py-2 flex items-center gap-3 text-[13px]">
          <span className="text-[#00D9FF]">$</span>
          <input
            type="text"
            value={commandInput}
            onChange={(e) => setCommandInput(e.target.value)}
            placeholder="Commands: attribution <id> | gdpr delete <id> | optimize tiers | analyze hallucinations | export report"
            className="flex-1 bg-transparent border-none text-[#00D9FF] font-mono text-[13px] outline-none placeholder:text-white/80"
          />
          <span className="text-white/85 tabular-nums">
            {agents.length} AGENTS • {total.totalContradictions} CONTRADICTIONS • {(total.totalTokens / 1000000).toFixed(1)}M TOK
          </span>
        </div>
      </div>
    </div>
  );
}
