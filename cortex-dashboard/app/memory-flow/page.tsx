'use client';

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Zap, AlertTriangle, TrendingUp, Database, GitBranch, Shield, DollarSign, Brain } from 'lucide-react';
import { Navigation } from '@/components/Navigation';

/**
 * INTERACTIVE MEMORY FLOW VISUALIZATION
 *
 * Demonstrates end-to-end memory attribution:
 * 1. Query arrives → Memory retrieval
 * 2. Attribution analysis (Shapley values)
 * 3. Memory impact visualization
 * 4. Cost/benefit analysis
 * 5. Root-cause tracing for hallucinations
 * 6. GDPR provenance chains
 */

interface Memory {
  id: string;
  content: string;
  timestamp: string;
  shapleyValue: number;
  tokenCost: number;
  retrievalRank: number;
  tier: 'hot' | 'warm' | 'cold';
  safetyLevel: 'critical' | 'normal' | 'low';
  contradictions: number;
  derivedFrom?: string[];
}

const SAMPLE_MEMORIES: Memory[] = [
  { id: 'M001', content: 'User subscription renews monthly on 15th', timestamp: '2025-11-12', shapleyValue: 0.73, tokenCost: 145, retrievalRank: 1, tier: 'hot', safetyLevel: 'normal', contradictions: 1, derivedFrom: ['C042', 'C089'] },
  { id: 'M198', content: 'User cancelled subscription on Feb 1, 2026', timestamp: '2026-02-01', shapleyValue: 0.12, tokenCost: 138, retrievalRank: 4, tier: 'warm', safetyLevel: 'critical', contradictions: 0, derivedFrom: ['C234'] },
  { id: 'M043', content: 'User prefers email notifications', timestamp: '2025-10-23', shapleyValue: 0.08, tokenCost: 112, retrievalRank: 2, tier: 'hot', safetyLevel: 'normal', contradictions: 0, derivedFrom: ['C021'] },
  { id: 'M089', content: 'User allergic to peanuts', timestamp: '2025-09-15', shapleyValue: 0.02, tokenCost: 98, retrievalRank: 7, tier: 'hot', safetyLevel: 'critical', contradictions: 0, derivedFrom: ['C012'] },
  { id: 'M124', content: 'User timezone is EST', timestamp: '2025-08-30', shapleyValue: 0.04, tokenCost: 87, retrievalRank: 3, tier: 'warm', safetyLevel: 'low', contradictions: 0, derivedFrom: ['C156'] },
  { id: 'M156', content: 'User company is TechCorp Inc', timestamp: '2025-07-18', shapleyValue: 0.01, tokenCost: 102, retrievalRank: 8, tier: 'cold', safetyLevel: 'low', contradictions: 0, derivedFrom: ['C078'] },
];

const SAMPLE_QUERY = "When does my subscription renew?";
const HALLUCINATED_RESPONSE = "Your subscription renews on March 15th.";
const GROUND_TRUTH = "Subscription was cancelled on February 1st, 2026.";

export default function MemoryFlowPage() {
  const [activeStep, setActiveStep] = React.useState<'idle' | 'query' | 'retrieval' | 'attribution' | 'analysis' | 'diagnosis'>('idle');
  const [selectedMemory, setSelectedMemory] = React.useState<Memory | null>(null);
  const [showProvenance, setShowProvenance] = React.useState(false);
  const [highlightedMemory, setHighlightedMemory] = React.useState<string | null>(null);

  // Auto-progress demo
  const startDemo = () => {
    setActiveStep('query');
    setTimeout(() => setActiveStep('retrieval'), 1500);
    setTimeout(() => setActiveStep('attribution'), 3000);
    setTimeout(() => setActiveStep('analysis'), 5000);
    setTimeout(() => {
      setActiveStep('diagnosis');
      setHighlightedMemory('M001');
    }, 7000);
  };

  const resetDemo = () => {
    setActiveStep('idle');
    setSelectedMemory(null);
    setHighlightedMemory(null);
  };

  const totalTokenCost = SAMPLE_MEMORIES.reduce((s, m) => s + m.tokenCost, 0);
  const wastedTokens = SAMPLE_MEMORIES.filter(m => m.shapleyValue < 0.05).reduce((s, m) => s + m.tokenCost, 0);
  const wastePercentage = (wastedTokens / totalTokenCost) * 100;

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white font-mono p-4 relative overflow-hidden">
      {/* Background Pattern */}
      <div className="fixed inset-0 opacity-[0.02] pointer-events-none" style={{
        backgroundImage: 'radial-gradient(circle at 2px 2px, #00D9FF 1px, transparent 0)',
        backgroundSize: '32px 32px'
      }} />

      <Navigation />

      {/* Header */}
      <div className="mb-4 flex justify-between items-center pt-16 relative z-10">
        <div>
          <h1 className="text-2xl font-bold text-[#00D9FF] mb-1">CORTEX MEMORY ATTRIBUTION DEMO</h1>
          <p className="text-xs text-white/50">End-to-end memory observability • Live root-cause analysis</p>
        </div>
        <div className="flex gap-2">
          <motion.button
            onClick={startDemo}
            disabled={activeStep !== 'idle'}
            className="px-5 py-2.5 bg-gradient-to-r from-[#00D9FF] to-[#00B8D4] text-black font-bold rounded disabled:opacity-50 disabled:cursor-not-allowed shadow-lg shadow-[#00D9FF]/20"
            whileHover={activeStep === 'idle' ? { scale: 1.05, boxShadow: '0 0 30px rgba(0, 217, 255, 0.4)' } : {}}
            whileTap={activeStep === 'idle' ? { scale: 0.95 } : {}}
          >
            ▶ START DEMO
          </motion.button>
          <motion.button
            onClick={resetDemo}
            className="px-5 py-2.5 bg-white/5 border border-white/20 text-white font-bold rounded hover:bg-white/10 transition-colors"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            ↻ RESET
          </motion.button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-3 relative z-10">

        {/* LEFT: Query Flow */}
        <div className="col-span-2 space-y-3">

          {/* Step 1: Query Input */}
          <motion.div
            className="bg-gradient-to-br from-[#111] to-[#0A0A0A] border-2 rounded-lg p-4 relative overflow-hidden"
            style={{ borderColor: activeStep === 'query' ? '#00D9FF' : '#333' }}
            animate={{
              borderColor: activeStep === 'query' ? '#00D9FF' : '#333',
              boxShadow: activeStep === 'query' ? '0 0 20px rgba(0, 217, 255, 0.2)' : '0 0 0 rgba(0, 217, 255, 0)'
            }}
          >
            {/* Grid pattern background */}
            <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: 'linear-gradient(#00D9FF 1px, transparent 1px), linear-gradient(90deg, #00D9FF 1px, transparent 1px)',
              backgroundSize: '20px 20px'
            }} />
            <div className="flex items-center gap-3 mb-3 relative z-10">
              <motion.div
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${activeStep === 'query' || activeStep !== 'idle' ? 'bg-gradient-to-br from-[#00D9FF] to-[#00B8D4] shadow-lg shadow-[#00D9FF]/30' : 'bg-white/10'}`}
                animate={activeStep === 'query' ? { scale: [1, 1.1, 1] } : {}}
                transition={{ duration: 0.6, repeat: activeStep === 'query' ? Infinity : 0 }}
              >
                <span className="text-lg font-bold">1</span>
              </motion.div>
              <div>
                <h3 className="text-base font-bold text-white">INCOMING QUERY</h3>
                <p className="text-2xs text-white/50">User submits question to agent</p>
              </div>
            </div>

            <AnimatePresence>
              {activeStep !== 'idle' && (
                <motion.div
                  initial={{ opacity: 0, y: 10, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  className="bg-gradient-to-br from-[#00D9FF]/10 to-transparent border border-[#00D9FF]/30 rounded p-3 relative z-10 shadow-lg shadow-[#00D9FF]/10"
                >
                  <div className="text-xs text-white/70 mb-2">USER QUERY:</div>
                  <div className="text-base font-bold text-[#00D9FF]">&ldquo;{SAMPLE_QUERY}&rdquo;</div>
                  <div className="mt-2 text-2xs text-white/40 flex items-center gap-3">
                    <span>🕐 {new Date().toISOString()}</span>
                    <span>•</span>
                    <span>Session: ABC-123</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Step 2: Memory Retrieval */}
          <motion.div
            className="bg-gradient-to-br from-[#111] to-[#0A0A0A] border-2 rounded-lg p-4 relative overflow-hidden"
            style={{ borderColor: activeStep === 'retrieval' ? '#00D9FF' : '#333' }}
            animate={{
              borderColor: activeStep === 'retrieval' ? '#00D9FF' : '#333',
              boxShadow: activeStep === 'retrieval' ? '0 0 20px rgba(0, 217, 255, 0.2)' : '0 0 0 rgba(0, 217, 255, 0)'
            }}
          >
            {/* Radial gradient pattern */}
            <div className="absolute inset-0 opacity-[0.03]" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, #00D9FF 1px, transparent 0)',
              backgroundSize: '24px 24px'
            }} />

            <div className="flex items-center gap-3 mb-3 relative z-10">
              <motion.div
                className={`w-10 h-10 rounded-full flex items-center justify-center transition-all ${activeStep === 'retrieval' || (activeStep !== 'idle' && activeStep !== 'query') ? 'bg-gradient-to-br from-[#00D9FF] to-[#00B8D4] shadow-lg shadow-[#00D9FF]/30' : 'bg-white/10'}`}
                animate={activeStep === 'retrieval' ? { scale: [1, 1.1, 1] } : {}}
                transition={{ duration: 0.6, repeat: activeStep === 'retrieval' ? Infinity : 0 }}
              >
                <span className="text-lg font-bold">2</span>
              </motion.div>
              <div>
                <h3 className="text-base font-bold text-white">MEMORY RETRIEVAL</h3>
                <p className="text-2xs text-white/50">Vector search retrieves relevant memories</p>
              </div>
            </div>

            <AnimatePresence>
              {(activeStep === 'retrieval' || activeStep === 'attribution' || activeStep === 'analysis' || activeStep === 'diagnosis') && (
                <motion.div className="space-y-2 relative z-10">
                  {SAMPLE_MEMORIES.slice(0, 5).map((mem, i) => (
                    <motion.div
                      key={mem.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className={`bg-gradient-to-br from-white/5 to-transparent border rounded p-2.5 cursor-pointer transition-all relative overflow-hidden ${
                        highlightedMemory === mem.id ? 'border-[#FF3A5E] bg-[#FF3A5E]/10 shadow-lg shadow-[#FF3A5E]/20' : 'border-white/10 hover:border-white/30'
                      }`}
                      onClick={() => setSelectedMemory(mem)}
                      whileHover={{ scale: 1.02, y: -2 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      {/* Shine effect on hover */}
                      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/5 to-transparent opacity-0 hover:opacity-100 transition-opacity pointer-events-none" />
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-[#00D9FF]">{mem.id}</span>
                            <span className="text-2xs text-white/40">Rank #{mem.retrievalRank}</span>
                            {mem.safetyLevel === 'critical' && (
                              <span className="text-2xs bg-[#FF3A5E]/20 text-[#FF3A5E] px-1.5 py-0.5 rounded">CRITICAL</span>
                            )}
                          </div>
                          <div className="text-sm text-white/80">{mem.content}</div>
                          <div className="flex items-center gap-3 mt-2 text-2xs text-white/50">
                            <span>📅 {mem.timestamp}</span>
                            <span>🪙 {mem.tokenCost} tokens</span>
                            <span className={`${mem.contradictions > 0 ? 'text-[#FFB800]' : ''}`}>
                              ⚠️ {mem.contradictions} contradictions
                            </span>
                          </div>
                        </div>
                      </div>
                    </motion.div>
                  ))}
                  <div className="text-xs text-white/40 text-center pt-2">
                    Retrieved 6 memories • {totalTokenCost} tokens • 8.2ms latency
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Step 3: Attribution Analysis */}
          <motion.div
            className="bg-[#111] border-2 rounded-lg p-6"
            style={{ borderColor: activeStep === 'attribution' ? '#00D9FF' : '#333' }}
            animate={{ borderColor: activeStep === 'attribution' ? '#00D9FF' : '#333' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${activeStep === 'attribution' || activeStep === 'analysis' || activeStep === 'diagnosis' ? 'bg-[#00D9FF]' : 'bg-white/10'}`}>
                <span className="text-lg font-bold">3</span>
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">SHAPLEY ATTRIBUTION</h3>
                <p className="text-xs text-white/50">Computing causal influence per memory</p>
              </div>
            </div>

            <AnimatePresence>
              {(activeStep === 'attribution' || activeStep === 'analysis' || activeStep === 'diagnosis') && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <div className="bg-white/5 border border-white/10 rounded p-4 mb-4">
                    <div className="text-xs text-white/50 mb-3">SHAPLEY VALUE DISTRIBUTION</div>
                    <div className="space-y-2">
                      {SAMPLE_MEMORIES.slice(0, 5).map((mem) => (
                        <div key={mem.id} className="flex items-center gap-3">
                          <span className="text-xs text-white/70 w-12">{mem.id}</span>
                          <div className="flex-1 h-6 bg-white/5 rounded-full overflow-hidden">
                            <motion.div
                              className="h-full rounded-full"
                              initial={{ width: 0 }}
                              animate={{ width: `${mem.shapleyValue * 100}%` }}
                              transition={{ duration: 0.8, delay: 0.2 }}
                              style={{
                                background: mem.shapleyValue > 0.5 ? '#FF3A5E' : mem.shapleyValue > 0.1 ? '#FFB800' : '#00FF88'
                              }}
                            />
                          </div>
                          <span className={`text-sm font-bold tabular-nums w-16 text-right ${
                            mem.shapleyValue > 0.5 ? 'text-[#FF3A5E]' : mem.shapleyValue > 0.1 ? 'text-[#FFB800]' : 'text-[#00FF88]'
                          }`}>
                            {(mem.shapleyValue * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    <div className="bg-[#00FF88]/10 border border-[#00FF88]/30 rounded p-3">
                      <div className="text-2xs text-white/50 mb-1">HIGH IMPACT</div>
                      <div className="text-xl font-bold text-[#00FF88]">
                        {SAMPLE_MEMORIES.filter(m => m.shapleyValue > 0.1).length}
                      </div>
                    </div>
                    <div className="bg-[#FFB800]/10 border border-[#FFB800]/30 rounded p-3">
                      <div className="text-2xs text-white/50 mb-1">LOW IMPACT</div>
                      <div className="text-xl font-bold text-[#FFB800]">
                        {SAMPLE_MEMORIES.filter(m => m.shapleyValue <= 0.1 && m.shapleyValue > 0.05).length}
                      </div>
                    </div>
                    <div className="bg-[#FF3A5E]/10 border border-[#FF3A5E]/30 rounded p-3">
                      <div className="text-2xs text-white/50 mb-1">WASTED</div>
                      <div className="text-xl font-bold text-[#FF3A5E]">
                        {SAMPLE_MEMORIES.filter(m => m.shapleyValue < 0.05).length}
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>

          {/* Step 4: Diagnosis */}
          <motion.div
            className="bg-[#111] border-2 rounded-lg p-6"
            style={{ borderColor: activeStep === 'diagnosis' ? '#FF3A5E' : '#333' }}
            animate={{ borderColor: activeStep === 'diagnosis' ? '#FF3A5E' : '#333' }}
          >
            <div className="flex items-center gap-3 mb-4">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center ${activeStep === 'diagnosis' ? 'bg-[#FF3A5E]' : 'bg-white/10'}`}>
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">ROOT-CAUSE DIAGNOSIS</h3>
                <p className="text-xs text-white/50">Hallucination detected • Tracing memory chain</p>
              </div>
            </div>

            <AnimatePresence>
              {activeStep === 'diagnosis' && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="space-y-4"
                >
                  <div className="bg-[#FF3A5E]/10 border border-[#FF3A5E]/30 rounded p-4">
                    <div className="text-xs text-white/50 mb-2">⚠️ FLAGGED RESPONSE:</div>
                    <div className="text-sm text-white font-bold mb-3">&ldquo;{HALLUCINATED_RESPONSE}&rdquo;</div>
                    <div className="text-xs text-white/50 mb-1">✓ GROUND TRUTH:</div>
                    <div className="text-sm text-[#00FF88]">{GROUND_TRUTH}</div>
                  </div>

                  <div className="bg-[#FFB800]/10 border border-[#FFB800]/30 rounded p-4">
                    <div className="text-sm font-bold text-[#FFB800] mb-3">🔍 ROOT CAUSE IDENTIFIED</div>
                    <div className="space-y-3">
                      <div>
                        <div className="text-xs text-white/50 mb-1">PRIMARY CONTRIBUTOR:</div>
                        <div className="bg-white/5 rounded p-2 border-l-4 border-[#FF3A5E]">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-[#FF3A5E]">Memory M001</span>
                            <span className="text-xs text-white/70">Attribution: 73%</span>
                          </div>
                          <div className="text-sm text-white">&ldquo;{SAMPLE_MEMORIES[0].content}&rdquo;</div>
                          <div className="text-2xs text-[#FF3A5E] mt-2">⚠️ STALE — Superseded by M198</div>
                        </div>
                      </div>

                      <div>
                        <div className="text-xs text-white/50 mb-1">CORRECT MEMORY (UNDERRANKED):</div>
                        <div className="bg-white/5 rounded p-2 border-l-4 border-[#00FF88]">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-xs font-bold text-[#00FF88]">Memory M198</span>
                            <span className="text-xs text-white/70">Attribution: 12%</span>
                          </div>
                          <div className="text-sm text-white">&ldquo;{SAMPLE_MEMORIES[1].content}&rdquo;</div>
                          <div className="text-2xs text-[#FFB800] mt-2">⬆️ Retrieval Rank: #4 (should be #1)</div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-[#00D9FF]/10 border border-[#00D9FF]/30 rounded p-4">
                    <div className="text-sm font-bold text-[#00D9FF] mb-2">💡 RECOMMENDED ACTIONS</div>
                    <div className="space-y-2 text-sm">
                      <div className="flex items-start gap-2">
                        <span className="text-[#00D9FF]">1.</span>
                        <span className="text-white/80">Invalidate M001 (contradiction detected with M198)</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-[#00D9FF]">2.</span>
                        <span className="text-white/80">Boost recency weight in retrieval algorithm</span>
                      </div>
                      <div className="flex items-start gap-2">
                        <span className="text-[#00D9FF]">3.</span>
                        <span className="text-white/80">Pin M198 as safety-critical (subscription status)</span>
                      </div>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white/5 border border-white/10 rounded p-3">
                      <div className="text-2xs text-white/50 mb-1">ESTIMATED COST</div>
                      <div className="text-lg font-bold text-[#FF3A5E]">$360/day</div>
                      <div className="text-2xs text-white/40">45 similar hallucinations</div>
                    </div>
                    <div className="bg-white/5 border border-white/10 rounded p-3">
                      <div className="text-2xs text-white/50 mb-1">TIME TO DIAGNOSE</div>
                      <div className="text-lg font-bold text-[#00FF88]">3.2 sec</div>
                      <div className="text-2xs text-white/40">vs 30-60 min manual</div>
                    </div>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        </div>

        {/* RIGHT: Live Metrics & Controls */}
        <div className="space-y-4">

          {/* Token Economics */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-gradient-to-br from-[#111] to-[#0A0A0A] border border-white/10 rounded-lg p-3 relative overflow-hidden"
            whileHover={{ borderColor: 'rgba(255, 184, 0, 0.3)' }}
          >
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-[0.02]" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, #FFB800 1px, transparent 0)',
              backgroundSize: '16px 16px'
            }} />

            <h3 className="text-xs font-bold text-white mb-3 flex items-center gap-2 relative z-10">
              <DollarSign size={14} className="text-[#FFB800]" />
              TOKEN ECONOMICS
            </h3>
            <div className="space-y-2.5 relative z-10">
              <div>
                <div className="flex justify-between text-2xs mb-1.5">
                  <span className="text-white/50">Total Cost</span>
                  <span className="text-white font-bold tabular-nums">{totalTokenCost} tok</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-[#00D9FF] to-[#00B8D4] rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: '100%' }}
                    transition={{ duration: 0.8, delay: 0.2 }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between text-2xs mb-1.5">
                  <span className="text-white/50">Wasted</span>
                  <span className="text-[#FF3A5E] font-bold tabular-nums">{wastedTokens} tok ({wastePercentage.toFixed(0)}%)</span>
                </div>
                <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-[#FF3A5E] to-[#FF1744] rounded-full"
                    initial={{ width: 0 }}
                    animate={{ width: `${wastePercentage}%` }}
                    transition={{ duration: 0.8, delay: 0.4 }}
                  />
                </div>
              </div>
              <motion.div
                className="bg-gradient-to-br from-[#FFB800]/10 to-transparent border border-[#FFB800]/30 rounded p-2 mt-2"
                whileHover={{ scale: 1.02, borderColor: 'rgba(255, 184, 0, 0.5)' }}
              >
                <div className="text-2xs text-white/50 mb-0.5">RECOVERABLE</div>
                <div className="text-lg font-bold text-[#FFB800]">$105/day</div>
                <div className="text-2xs text-white/40">$38K/year at scale</div>
              </motion.div>
            </div>
          </motion.div>

          {/* Memory Details */}
          {selectedMemory && (
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#111] border border-[#00D9FF]/50 rounded-lg p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-bold text-[#00D9FF]">MEMORY DETAILS</h3>
                <button onClick={() => setSelectedMemory(null)} className="text-white/50 hover:text-white">✕</button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <div className="text-white/50 mb-1">ID:</div>
                  <div className="text-white font-bold">{selectedMemory.id}</div>
                </div>
                <div>
                  <div className="text-white/50 mb-1">Content:</div>
                  <div className="text-white">{selectedMemory.content}</div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-white/50 mb-1">Shapley:</div>
                    <div className="text-[#00D9FF] font-bold tabular-nums">{(selectedMemory.shapleyValue * 100).toFixed(0)}%</div>
                  </div>
                  <div>
                    <div className="text-white/50 mb-1">Cost:</div>
                    <div className="text-[#FFB800] font-bold tabular-nums">{selectedMemory.tokenCost} tok</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <div className="text-white/50 mb-1">Tier:</div>
                    <div className="text-white font-bold uppercase">{selectedMemory.tier}</div>
                  </div>
                  <div>
                    <div className="text-white/50 mb-1">Safety:</div>
                    <div className={`font-bold uppercase ${selectedMemory.safetyLevel === 'critical' ? 'text-[#FF3A5E]' : 'text-white'}`}>
                      {selectedMemory.safetyLevel}
                    </div>
                  </div>
                </div>

                <button
                  onClick={() => setShowProvenance(true)}
                  className="w-full py-2 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded text-xs font-bold hover:bg-[#00D9FF]/30 transition-colors"
                >
                  🔗 VIEW PROVENANCE CHAIN
                </button>
              </div>
            </motion.div>
          )}

          {/* System Stats */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="bg-gradient-to-br from-[#111] to-[#0A0A0A] border border-white/10 rounded-lg p-3 relative overflow-hidden"
            whileHover={{ borderColor: 'rgba(0, 255, 136, 0.3)' }}
          >
            {/* Background pattern */}
            <div className="absolute inset-0 opacity-[0.02]" style={{
              backgroundImage: 'radial-gradient(circle at 2px 2px, #00FF88 1px, transparent 0)',
              backgroundSize: '16px 16px'
            }} />

            <h3 className="text-xs font-bold text-white mb-3 flex items-center gap-2 relative z-10">
              <Brain size={14} className="text-[#00FF88]" />
              SYSTEM HEALTH
            </h3>
            <div className="space-y-2 text-2xs relative z-10">
              <motion.div
                className="flex justify-between p-1.5 bg-white/5 rounded hover:bg-white/10 transition-colors"
                whileHover={{ x: 2 }}
              >
                <span className="text-white/50">Attribution Accuracy</span>
                <span className="text-[#00FF88] font-bold tabular-nums">94.2%</span>
              </motion.div>
              <motion.div
                className="flex justify-between p-1.5 bg-white/5 rounded hover:bg-white/10 transition-colors"
                whileHover={{ x: 2 }}
              >
                <span className="text-white/50">Avg Latency</span>
                <span className="text-[#00D9FF] font-bold tabular-nums">8.2ms</span>
              </motion.div>
              <motion.div
                className="flex justify-between p-1.5 bg-white/5 rounded hover:bg-white/10 transition-colors"
                whileHover={{ x: 2 }}
              >
                <span className="text-white/50">Memory Store Size</span>
                <span className="text-white font-bold tabular-nums">3,247</span>
              </motion.div>
              <motion.div
                className="flex justify-between p-1.5 bg-white/5 rounded hover:bg-white/10 transition-colors"
                whileHover={{ x: 2 }}
              >
                <span className="text-white/50">Contradictions</span>
                <span className="text-[#FFB800] font-bold tabular-nums">12</span>
              </motion.div>
              <motion.div
                className="flex justify-between p-1.5 bg-white/5 rounded hover:bg-white/10 transition-colors"
                whileHover={{ x: 2 }}
              >
                <span className="text-white/50">GDPR Pending</span>
                <span className="text-[#FF3A5E] font-bold tabular-nums">8</span>
              </motion.div>
            </div>
          </motion.div>

          {/* Quick Actions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="bg-gradient-to-br from-[#111] to-[#0A0A0A] border border-white/10 rounded-lg p-3"
          >
            <h3 className="text-xs font-bold text-white mb-2.5">QUICK ACTIONS</h3>
            <div className="space-y-1.5">
              <motion.button
                className="w-full py-2 bg-gradient-to-r from-white/5 to-transparent border border-white/20 text-white text-2xs rounded hover:border-[#00D9FF]/40 transition-colors flex items-center gap-2 justify-center font-bold"
                whileHover={{ scale: 1.03, x: 2, backgroundColor: 'rgba(0, 217, 255, 0.1)' }}
                whileTap={{ scale: 0.97 }}
              >
                <Zap size={12} className="text-[#00D9FF]" />
                Archive Low-Impact
              </motion.button>
              <motion.button
                className="w-full py-2 bg-gradient-to-r from-white/5 to-transparent border border-white/20 text-white text-2xs rounded hover:border-[#00FF88]/40 transition-colors flex items-center gap-2 justify-center font-bold"
                whileHover={{ scale: 1.03, x: 2, backgroundColor: 'rgba(0, 255, 136, 0.1)' }}
                whileTap={{ scale: 0.97 }}
              >
                <TrendingUp size={12} className="text-[#00FF88]" />
                Optimize Retrieval
              </motion.button>
              <motion.button
                className="w-full py-2 bg-gradient-to-r from-white/5 to-transparent border border-white/20 text-white text-2xs rounded hover:border-[#FFB800]/40 transition-colors flex items-center gap-2 justify-center font-bold"
                whileHover={{ scale: 1.03, x: 2, backgroundColor: 'rgba(255, 184, 0, 0.1)' }}
                whileTap={{ scale: 0.97 }}
              >
                <Shield size={12} className="text-[#FFB800]" />
                Resolve Contradictions
              </motion.button>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Provenance Modal */}
      <AnimatePresence>
        {showProvenance && selectedMemory && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-6"
            onClick={() => setShowProvenance(false)}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.9, y: 20 }}
              className="bg-[#0A0A0A] border-2 border-[#00D9FF] rounded-lg p-6 max-w-2xl w-full"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-[#00D9FF]">GDPR PROVENANCE CHAIN</h2>
                <button onClick={() => setShowProvenance(false)} className="text-white/50 hover:text-white text-xl">✕</button>
              </div>

              <div className="space-y-4">
                <div className="bg-white/5 border border-white/10 rounded p-4">
                  <div className="text-xs text-white/50 mb-2">TARGET MEMORY:</div>
                  <div className="text-sm font-bold text-white mb-1">{selectedMemory.id}</div>
                  <div className="text-sm text-white/70">{selectedMemory.content}</div>
                </div>

                <div className="flex items-center justify-center">
                  <GitBranch size={24} className="text-[#00D9FF]" />
                </div>

                <div className="bg-white/5 border border-white/10 rounded p-4">
                  <div className="text-xs text-white/50 mb-3">DERIVED FROM:</div>
                  {selectedMemory.derivedFrom?.map((sourceId, i) => (
                    <motion.div
                      key={i}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.1 }}
                      className="bg-white/5 border border-white/10 rounded p-2 mb-2"
                    >
                      <div className="text-xs font-bold text-[#00D9FF]">Conversation {sourceId}</div>
                      <div className="text-2xs text-white/50 mt-1">Timestamp: 2026-01-{15 + i} • User: john@example.com</div>
                    </motion.div>
                  ))}
                </div>

                <div className="bg-[#FF3A5E]/10 border border-[#FF3A5E]/30 rounded p-4">
                  <div className="text-sm font-bold text-[#FF3A5E] mb-2">⚠️ DELETION IMPACT</div>
                  <div className="text-xs text-white/70 space-y-1">
                    <div>• Will invalidate {selectedMemory.derivedFrom?.length} source conversations</div>
                    <div>• Will remove from 3 embeddings</div>
                    <div>• Will cascade to 8 downstream memories</div>
                    <div>• 30-day grace period before hard deletion</div>
                  </div>
                </div>

                <motion.button
                  className="w-full py-3 bg-[#FF3A5E] text-white font-bold rounded"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  🗑️ INITIATE GDPR DELETION
                </motion.button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
