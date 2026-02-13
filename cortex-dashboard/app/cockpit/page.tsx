'use client';

import React from 'react';
import { Navigation } from '@/components/Navigation';
import {
  Zap, AlertTriangle, TrendingUp, Activity, Eye, Edit3, Trash2,
  GitBranch, Shield, DollarSign, Brain, Clock, Target, Sliders,
  PlayCircle, PauseCircle, RotateCcw, CheckCircle, XCircle,
  ArrowRight, Info, Search, Filter, Save, Upload
} from 'lucide-react';

/**
 * CORTEX COCKPIT - Full Featured Memory Management
 *
 * 7 Modes:
 * 1. Overview - Memory tier visualization with drag-drop
 * 2. Timeline - Memory evolution scrubber
 * 3. Live Editor - Edit memories with impact preview
 * 4. Optimizer - A/B testing with sliders
 * 5. Resolver - Contradiction resolution
 * 6. Blast Radius - Impact calculator
 * 7. Audit - Compliance trail
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
  affectedResponses: number;
  lastAccessed: string;
  source: string;
  confidence: number;
}

const CRITICAL_SCENARIO_MEMORIES: Memory[] = [
  {
    id: 'M001',
    content: 'Patient takes Warfarin 5mg daily',
    timestamp: '2025-11-12',
    shapleyValue: 0.82,
    tokenCost: 145,
    retrievalRank: 1,
    tier: 'hot',
    safetyLevel: 'critical',
    contradictions: 1,
    affectedResponses: 247,
    lastAccessed: '2026-02-11 14:23',
    source: 'Initial consultation',
    confidence: 0.95
  },
  {
    id: 'M089',
    content: 'Patient switched to Eliquis 5mg after adverse reaction',
    timestamp: '2026-01-15',
    shapleyValue: 0.08,
    tokenCost: 162,
    retrievalRank: 8,
    tier: 'warm',
    safetyLevel: 'critical',
    contradictions: 0,
    affectedResponses: 12,
    lastAccessed: '2026-02-11 14:22',
    source: 'Follow-up visit',
    confidence: 0.98
  },
  {
    id: 'M043',
    content: 'Patient allergic to penicillin',
    timestamp: '2025-09-03',
    shapleyValue: 0.03,
    tokenCost: 98,
    retrievalRank: 5,
    tier: 'hot',
    safetyLevel: 'critical',
    contradictions: 0,
    affectedResponses: 89,
    lastAccessed: '2026-02-10 09:15',
    source: 'Allergy screening',
    confidence: 1.0
  },
  {
    id: 'M124',
    content: 'Patient prefers morning appointments',
    timestamp: '2025-08-20',
    shapleyValue: 0.02,
    tokenCost: 87,
    retrievalRank: 12,
    tier: 'cold',
    safetyLevel: 'low',
    contradictions: 0,
    affectedResponses: 4,
    lastAccessed: '2026-01-20 11:30',
    source: 'Preference survey',
    confidence: 0.88
  },
  {
    id: 'M067',
    content: 'Patient has history of hypertension',
    timestamp: '2025-10-05',
    shapleyValue: 0.12,
    tokenCost: 112,
    retrievalRank: 3,
    tier: 'warm',
    safetyLevel: 'normal',
    contradictions: 0,
    affectedResponses: 56,
    lastAccessed: '2026-02-09 16:45',
    source: 'Medical history',
    confidence: 0.97
  }
];

type Mode = 'overview' | 'timeline' | 'editor' | 'optimizer' | 'resolver' | 'blast' | 'audit';

export default function CockpitPage() {
  const [mode, setMode] = React.useState<Mode>('overview');
  const [memories, setMemories] = React.useState<Memory[]>(CRITICAL_SCENARIO_MEMORIES);
  const [selectedMemory, setSelectedMemory] = React.useState<Memory | null>(null);
  const [draggedMemory, setDraggedMemory] = React.useState<Memory | null>(null);
  const [alert, setAlert] = React.useState<{ type: 'success' | 'warning' | 'error', message: string } | null>(null);
  const [isResolving, setIsResolving] = React.useState(false);

  // Optimizer state
  const [kValue, setKValue] = React.useState(8);
  const [recencyWeight, setRecencyWeight] = React.useState(0.3);
  const [safetyBoost, setSafetyBoost] = React.useState(2.0);

  // Timeline state
  const [timelinePosition, setTimelinePosition] = React.useState(100);

  // Editor state
  const [editContent, setEditContent] = React.useState('');

  // Handle tier change via drag and drop
  const handleTierChange = (memoryId: string, newTier: 'hot' | 'warm' | 'cold') => {
    setMemories(prev => prev.map(m =>
      m.id === memoryId ? { ...m, tier: newTier } : m
    ));
    setAlert({
      type: 'success',
      message: `${memoryId} moved to ${newTier.toUpperCase()} tier`
    });
    setTimeout(() => setAlert(null), 3000);
  };

  // Handle memory archive
  const handleArchive = (memoryId: string) => {
    const memory = memories.find(m => m.id === memoryId);
    if (memory) {
      setAlert({
        type: 'warning',
        message: `Archiving ${memoryId} will affect ${memory.affectedResponses} responses`
      });
      setTimeout(() => setAlert(null), 3000);
    }
  };

  // Handle save edited memory
  const handleSaveEdit = () => {
    if (selectedMemory) {
      setMemories(prev => prev.map(m =>
        m.id === selectedMemory.id ? { ...m, content: editContent } : m
      ));
      setAlert({
        type: 'success',
        message: `Memory ${selectedMemory.id} updated successfully`
      });
      setTimeout(() => setAlert(null), 3000);
    }
  };

  // Handle resolver actions
  const handleArchiveOlder = () => {
    setIsResolving(true);
    setAlert({
      type: 'warning',
      message: 'Processing... Archiving M001 and updating 247 affected responses'
    });

    setTimeout(() => {
      setMemories(prev => prev.filter(m => m.id !== 'M001'));
      setMemories(prev => prev.map(m =>
        m.id === 'M089' ? { ...m, contradictions: 0, shapleyValue: 0.82 } : m
      ));
      setAlert({
        type: 'success',
        message: 'M001 archived. M089 promoted to primary medication record. 247 responses re-ranked.'
      });
      setTimeout(() => {
        setAlert(null);
        setIsResolving(false);
        setMode('overview');
      }, 2000);
    }, 1500);
  };

  const handleMergeMemories = () => {
    setIsResolving(true);
    setAlert({
      type: 'warning',
      message: 'Processing... Merging memory timelines'
    });

    setTimeout(() => {
      setMemories(prev => prev.filter(m => m.id !== 'M001'));
      setMemories(prev => prev.map(m =>
        m.id === 'M089'
          ? {
              ...m,
              content: 'Patient medication history: Previously on Warfarin 5mg (2025-11-12), switched to Eliquis 5mg after adverse reaction (2026-01-15)',
              contradictions: 0,
              shapleyValue: 0.90
            }
          : m
      ));
      setAlert({
        type: 'success',
        message: 'Memories merged into single timeline record with full medication history'
      });
      setTimeout(() => {
        setAlert(null);
        setIsResolving(false);
        setMode('overview');
      }, 2000);
    }, 1500);
  };

  const handleKeepBoth = () => {
    setIsResolving(true);
    setAlert({
      type: 'warning',
      message: 'Processing... Adding temporal context markers'
    });

    setTimeout(() => {
      setMemories(prev => prev.map(m => {
        if (m.id === 'M001') {
          return { ...m, content: m.content + ' [DEPRECATED: See M089]', tier: 'cold', contradictions: 0 };
        }
        if (m.id === 'M089') {
          return { ...m, content: m.content + ' [SUPERSEDES: M001]', contradictions: 0 };
        }
        return m;
      }));
      setAlert({
        type: 'success',
        message: 'Temporal context added to both memories. M001 moved to COLD tier.'
      });
      setTimeout(() => {
        setAlert(null);
        setIsResolving(false);
        setMode('overview');
      }, 2000);
    }, 1500);
  };

  const handleRunABTest = () => {
    setAlert({
      type: 'success',
      message: `Running A/B test with k=${kValue}, recency=${recencyWeight.toFixed(2)}, safety=${safetyBoost.toFixed(1)}x on shadow traffic...`
    });
    setTimeout(() => {
      setAlert({
        type: 'success',
        message: 'A/B test complete! New config shows +4.6% accuracy improvement'
      });
    }, 2000);
    setTimeout(() => setAlert(null), 5000);
  };

  const handleExportReport = () => {
    const reportData = {
      timestamp: new Date().toISOString(),
      totalMemories: memories.length,
      contradictions: memories.filter(m => m.contradictions > 0).length,
      auditTrail: 'Full audit log exported',
      compliance: 'GDPR compliant'
    };

    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cortex-audit-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);

    setAlert({
      type: 'success',
      message: 'Audit report exported successfully'
    });
    setTimeout(() => setAlert(null), 3000);
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A] text-white font-mono">
      <Navigation />

      {/* Alert Banner */}
      {alert && (
        <div className={`fixed top-20 left-1/2 -translate-x-1/2 z-50 px-6 py-3 rounded-lg shadow-lg ${
          alert.type === 'success' ? 'bg-green-500/20 border border-green-500/50 text-green-400' :
          alert.type === 'warning' ? 'bg-yellow-500/20 border border-yellow-500/50 text-yellow-400' :
          'bg-red-500/20 border border-red-500/50 text-red-400'
        }`}>
          {alert.message}
        </div>
      )}

      {/* Top Bar - Compact spacing */}
      <div className="border-b border-white/10 bg-black/95 backdrop-blur-md px-6 py-3 sticky top-16 z-30 shadow-lg">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xl font-bold text-[#00D9FF]">CORTEX MISSION CONTROL</h1>
            <p className="text-xs text-white/80">Healthcare Agent • Patient ID: P-7829 • Real-time Memory Management</p>
          </div>

          {/* Critical Alert with pulse animation */}
          <div className="bg-[#FF3A5E]/20 border-2 border-[#FF3A5E] rounded-lg px-3 py-1.5 animate-pulse-slow">
            <div className="flex items-center gap-2">
              <AlertTriangle size={16} className="text-[#FF3A5E]" />
              <div>
                <div className="text-xs font-bold text-[#FF3A5E]">CONTRADICTION DETECTED</div>
                <div className="text-xs text-white/80">247 responses affected</div>
              </div>
            </div>
          </div>
        </div>

        {/* Mode Tabs */}
        <div className="flex gap-2 flex-wrap">
          {[
            { id: 'overview', label: 'Overview', icon: Eye },
            { id: 'timeline', label: 'Timeline', icon: Clock },
            { id: 'editor', label: 'Live Editor', icon: Edit3 },
            { id: 'optimizer', label: 'Optimizer', icon: Sliders },
            { id: 'resolver', label: 'Resolver', icon: GitBranch },
            { id: 'blast', label: 'Blast Radius', icon: Target },
            { id: 'audit', label: 'Audit Trail', icon: Shield },
          ].map((m) => {
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                onClick={() => setMode(m.id as Mode)}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all duration-300 transform hover:scale-105 ${
                  mode === m.id
                    ? 'bg-[#00D9FF] text-black shadow-lg shadow-[#00D9FF]/50'
                    : 'bg-white/5 text-white/70 hover:bg-white/10 hover:text-white'
                }`}
              >
                <Icon size={14} />
                {m.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="p-6 pt-32">
        {/* OVERVIEW MODE */}
        {mode === 'overview' && (
          <div className="grid grid-cols-4 gap-4 animate-fade-in">
            {/* Left: Critical Stats */}
            <div className="space-y-4 animate-slide-in-up">
              <div className="bg-[#111] border border-white/10 rounded-lg p-4">
                <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                  <Brain size={16} className="text-[#00D9FF]" />
                  MEMORY HEALTH
                </h3>
                <div className="space-y-3">
                  <div>
                    <div className="text-xs text-white/80 mb-1">Total Memories</div>
                    <div className="text-2xl font-bold text-white">{memories.length}</div>
                  </div>
                  <div>
                    <div className="text-xs text-white/80 mb-1">Avg Shapley Value</div>
                    <div className="text-2xl font-bold text-[#00D9FF]">
                      {(memories.reduce((acc, m) => acc + m.shapleyValue, 0) / memories.length).toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-white/80 mb-1">Contradictions</div>
                    <div className="text-2xl font-bold text-[#FF3A5E]">
                      {memories.filter(m => m.contradictions > 0).length}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-white/80 mb-1">Total Token Cost</div>
                    <div className="text-2xl font-bold text-[#FFB800]">
                      {memories.reduce((acc, m) => acc + m.tokenCost, 0)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Quick Actions */}
              <div className="bg-[#111] border border-white/10 rounded-lg p-4">
                <h3 className="text-sm font-bold text-white mb-3">QUICK ACTIONS</h3>
                <div className="space-y-2">
                  <button
                    onClick={() => setMode('resolver')}
                    className="w-full py-2 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] rounded text-xs font-bold hover:bg-[#FF3A5E]/30 transition-colors flex items-center gap-2 justify-center"
                  >
                    <AlertTriangle size={14} />
                    Resolve Contradiction
                  </button>

                  <button
                    onClick={() => setMode('blast')}
                    className="w-full py-2 bg-[#FFB800]/20 border border-[#FFB800]/40 text-[#FFB800] rounded text-xs font-bold hover:bg-[#FFB800]/30 transition-colors flex items-center gap-2 justify-center"
                  >
                    <Target size={14} />
                    Calculate Blast Radius
                  </button>

                  <button
                    onClick={() => setMode('optimizer')}
                    className="w-full py-2 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded text-xs font-bold hover:bg-[#00D9FF]/30 transition-colors flex items-center gap-2 justify-center"
                  >
                    <Sliders size={14} />
                    Optimize Retrieval
                  </button>
                </div>
              </div>
            </div>

            {/* Center: Memory Tiers (Drag & Drop) */}
            <div className="col-span-3 space-y-4">
              {/* HOT TIER */}
              <div
                className="bg-[#FF3A5E]/10 border-2 border-[#FF3A5E]/40 rounded-lg p-4 animate-scale-in transition-all duration-300 hover:shadow-lg hover:shadow-[#FF3A5E]/20"
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (draggedMemory && draggedMemory.safetyLevel === 'critical') {
                    setAlert({
                      type: 'error',
                      message: 'Cannot move critical safety memories'
                    });
                    setTimeout(() => setAlert(null), 3000);
                  } else if (draggedMemory) {
                    handleTierChange(draggedMemory.id, 'hot');
                  }
                  setDraggedMemory(null);
                }}
              >
                <h3 className="text-sm font-bold text-[#FF3A5E] mb-3 flex items-center gap-2">
                  <Zap size={16} />
                  HOT TIER (High Impact)
                </h3>
                <div className="space-y-2">
                  {memories.filter(m => m.tier === 'hot').map(memory => (
                    <div
                      key={memory.id}
                      draggable
                      onDragStart={() => setDraggedMemory(memory)}
                      onDragEnd={() => setDraggedMemory(null)}
                      className={`bg-[#111] border ${
                        memory.safetyLevel === 'critical'
                          ? 'border-[#FF3A5E] shadow-lg shadow-[#FF3A5E]/20'
                          : 'border-white/20'
                      } rounded-lg p-3 cursor-move hover:border-[#00D9FF] transition-colors`}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-bold text-[#00D9FF]">{memory.id}</span>
                            {memory.safetyLevel === 'critical' && (
                              <span className="text-xs px-2 py-0.5 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] rounded">
                                CRITICAL
                              </span>
                            )}
                            {memory.contradictions > 0 && (
                              <span className="text-xs px-2 py-0.5 bg-yellow-500/20 border border-yellow-500/40 text-yellow-400 rounded">
                                CONFLICT
                              </span>
                            )}
                          </div>
                          <div className="text-sm text-white/90 mb-2">{memory.content}</div>
                          <div className="flex items-center gap-4 text-xs">
                            <span className="text-white/80">
                              <strong className="text-[#00D9FF]">Shapley:</strong> {(memory.shapleyValue * 100).toFixed(0)}%
                            </span>
                            <span className="text-white/80">
                              <strong className="text-[#FFB800]">Cost:</strong> {memory.tokenCost}t
                            </span>
                            <span className="text-white/80">
                              <strong className="text-white/90">Affected:</strong> {memory.affectedResponses}
                            </span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedMemory(memory);
                              setEditContent(memory.content);
                              setMode('editor');
                            }}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Edit3 size={14} className="text-[#00D9FF]" />
                          </button>
                          <button
                            onClick={() => handleArchive(memory.id)}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Trash2 size={14} className="text-[#FF3A5E]" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* WARM TIER */}
              <div
                className="bg-[#FFB800]/10 border-2 border-[#FFB800]/40 rounded-lg p-4 animate-scale-in transition-all duration-300 hover:shadow-lg hover:shadow-[#FFB800]/20"
                style={{ animationDelay: '0.1s' }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (draggedMemory) {
                    handleTierChange(draggedMemory.id, 'warm');
                  }
                  setDraggedMemory(null);
                }}
              >
                <h3 className="text-sm font-bold text-[#FFB800] mb-3 flex items-center gap-2">
                  <Activity size={16} />
                  WARM TIER (Aging)
                </h3>
                <div className="space-y-2">
                  {memories.filter(m => m.tier === 'warm').map(memory => (
                    <div
                      key={memory.id}
                      draggable
                      onDragStart={() => setDraggedMemory(memory)}
                      onDragEnd={() => setDraggedMemory(null)}
                      className="bg-[#111] border border-white/20 rounded-lg p-3 cursor-move hover:border-[#00D9FF] transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-bold text-[#00D9FF]">{memory.id}</span>
                          </div>
                          <div className="text-sm text-white/90 mb-2">{memory.content}</div>
                          <div className="flex items-center gap-4 text-xs">
                            <span className="text-white/80">
                              <strong className="text-[#00D9FF]">Shapley:</strong> {(memory.shapleyValue * 100).toFixed(0)}%
                            </span>
                            <span className="text-white/80">
                              <strong className="text-[#FFB800]">Cost:</strong> {memory.tokenCost}t
                            </span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedMemory(memory);
                              setEditContent(memory.content);
                              setMode('editor');
                            }}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Edit3 size={14} className="text-[#00D9FF]" />
                          </button>
                          <button
                            onClick={() => handleArchive(memory.id)}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Trash2 size={14} className="text-[#FF3A5E]" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* COLD TIER */}
              <div
                className="bg-[#00D9FF]/10 border-2 border-[#00D9FF]/40 rounded-lg p-4 animate-scale-in transition-all duration-300 hover:shadow-lg hover:shadow-[#00D9FF]/20"
                style={{ animationDelay: '0.2s' }}
                onDragOver={(e) => e.preventDefault()}
                onDrop={(e) => {
                  e.preventDefault();
                  if (draggedMemory) {
                    handleTierChange(draggedMemory.id, 'cold');
                  }
                  setDraggedMemory(null);
                }}
              >
                <h3 className="text-sm font-bold text-[#00D9FF] mb-3 flex items-center gap-2">
                  <TrendingUp size={16} />
                  COLD TIER (Archive Candidates)
                </h3>
                <div className="space-y-2">
                  {memories.filter(m => m.tier === 'cold').map(memory => (
                    <div
                      key={memory.id}
                      draggable
                      onDragStart={() => setDraggedMemory(memory)}
                      onDragEnd={() => setDraggedMemory(null)}
                      className="bg-[#111] border border-white/20 rounded-lg p-3 cursor-move hover:border-[#00D9FF] transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <span className="text-xs font-bold text-[#00D9FF]">{memory.id}</span>
                          </div>
                          <div className="text-sm text-white/90 mb-2">{memory.content}</div>
                          <div className="flex items-center gap-4 text-xs">
                            <span className="text-white/80">
                              <strong className="text-[#00D9FF]">Shapley:</strong> {(memory.shapleyValue * 100).toFixed(0)}%
                            </span>
                            <span className="text-white/80">
                              <strong className="text-[#FFB800]">Cost:</strong> {memory.tokenCost}t
                            </span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setSelectedMemory(memory);
                              setEditContent(memory.content);
                              setMode('editor');
                            }}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Edit3 size={14} className="text-[#00D9FF]" />
                          </button>
                          <button
                            onClick={() => handleArchive(memory.id)}
                            className="p-2 bg-white/5 hover:bg-white/10 rounded transition-colors"
                          >
                            <Trash2 size={14} className="text-[#FF3A5E]" />
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TIMELINE MODE */}
        {mode === 'timeline' && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Clock size={20} className="text-[#00D9FF]" />
                Memory Evolution Timeline
              </h2>

              {/* Timeline Scrubber */}
              <div className="mb-6">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-white/80">Nov 2025</span>
                  <span className="text-sm text-[#00D9FF] font-bold">
                    {timelinePosition === 100 ? 'CURRENT' : `${timelinePosition}% of history`}
                  </span>
                  <span className="text-sm text-white/80">Feb 2026</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={timelinePosition}
                  onChange={(e) => setTimelinePosition(parseInt(e.target.value))}
                  className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, #00D9FF ${timelinePosition}%, rgba(255,255,255,0.1) ${timelinePosition}%)`
                  }}
                />
              </div>

              {/* Timeline Events */}
              <div className="space-y-4">
                <div className="border-l-2 border-[#00D9FF] pl-4 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full bg-[#FF3A5E] -ml-[26px]"></div>
                    <span className="text-xs text-white/80">2026-01-15</span>
                    <span className="text-xs px-2 py-0.5 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] rounded">
                      CONTRADICTION DETECTED
                    </span>
                  </div>
                  <div className="text-sm text-white/90">
                    M089 (Eliquis) conflicts with M001 (Warfarin) - 247 responses affected
                  </div>
                </div>

                <div className="border-l-2 border-[#00D9FF] pl-4 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full bg-[#00D9FF] -ml-[26px]"></div>
                    <span className="text-xs text-white/80">2025-11-12</span>
                    <span className="text-xs px-2 py-0.5 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded">
                      MEMORY CREATED
                    </span>
                  </div>
                  <div className="text-sm text-white/90">
                    M001 (Warfarin) added from initial consultation
                  </div>
                </div>

                <div className="border-l-2 border-[#00D9FF] pl-4 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full bg-[#FFB800] -ml-[26px]"></div>
                    <span className="text-xs text-white/80">2025-10-05</span>
                    <span className="text-xs px-2 py-0.5 bg-[#FFB800]/20 border border-[#FFB800]/40 text-[#FFB800] rounded">
                      TIER CHANGE
                    </span>
                  </div>
                  <div className="text-sm text-white/90">
                    M067 (Hypertension) moved from HOT → WARM tier
                  </div>
                </div>

                <div className="border-l-2 border-[#00D9FF] pl-4 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="w-3 h-3 rounded-full bg-green-500 -ml-[26px]"></div>
                    <span className="text-xs text-white/80">2025-09-03</span>
                    <span className="text-xs px-2 py-0.5 bg-green-500/20 border border-green-500/40 text-green-400 rounded">
                      CRITICAL ADDED
                    </span>
                  </div>
                  <div className="text-sm text-white/90">
                    M043 (Penicillin allergy) marked as critical safety memory
                  </div>
                </div>
              </div>
            </div>

            {/* Memory Snapshot at Timeline Position */}
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h3 className="text-lg font-bold text-white mb-4">
                Memory State at {timelinePosition}%
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-3xl font-bold text-[#FF3A5E]">
                    {memories.filter(m => m.tier === 'hot').length}
                  </div>
                  <div className="text-sm text-white/80">Hot Memories</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-[#FFB800]">
                    {memories.filter(m => m.tier === 'warm').length}
                  </div>
                  <div className="text-sm text-white/80">Warm Memories</div>
                </div>
                <div className="text-center">
                  <div className="text-3xl font-bold text-[#00D9FF]">
                    {memories.filter(m => m.tier === 'cold').length}
                  </div>
                  <div className="text-sm text-white/80">Cold Memories</div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* LIVE EDITOR MODE */}
        {mode === 'editor' && (
          <div className="grid grid-cols-2 gap-6 animate-fade-in">
            {/* Left: Memory Selector */}
            <div className="space-y-4">
              <div className="bg-[#111] border border-white/10 rounded-lg p-4">
                <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                  <Edit3 size={20} className="text-[#00D9FF]" />
                  Select Memory to Edit
                </h2>
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {memories.map(memory => (
                    <button
                      key={memory.id}
                      onClick={() => {
                        setSelectedMemory(memory);
                        setEditContent(memory.content);
                      }}
                      className={`w-full text-left p-3 rounded-lg border transition-colors ${
                        selectedMemory?.id === memory.id
                          ? 'bg-[#00D9FF]/20 border-[#00D9FF]'
                          : 'bg-[#0A0A0A] border-white/20 hover:border-[#00D9FF]/50'
                      }`}
                    >
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-[#00D9FF]">{memory.id}</span>
                        {memory.safetyLevel === 'critical' && (
                          <span className="text-xs px-2 py-0.5 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] rounded">
                            CRITICAL
                          </span>
                        )}
                      </div>
                      <div className="text-sm text-white/90">{memory.content}</div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Right: Editor */}
            <div className="space-y-4">
              {selectedMemory ? (
                <>
                  <div className="bg-[#111] border border-white/10 rounded-lg p-4">
                    <h3 className="text-lg font-bold text-white mb-4">
                      Editing {selectedMemory.id}
                    </h3>
                    <textarea
                      value={editContent}
                      onChange={(e) => setEditContent(e.target.value)}
                      className="w-full h-40 bg-[#0A0A0A] border border-white/20 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-[#00D9FF] resize-none"
                      placeholder="Edit memory content..."
                    />
                    <div className="flex gap-2 mt-4">
                      <button
                        onClick={handleSaveEdit}
                        className="flex-1 py-2 bg-[#00D9FF] text-black font-bold rounded-lg hover:bg-[#00D9FF]/80 transition-colors flex items-center gap-2 justify-center"
                      >
                        <Save size={16} />
                        Save Changes
                      </button>
                      <button
                        onClick={() => setEditContent(selectedMemory.content)}
                        className="px-4 py-2 bg-white/5 text-white/70 font-bold rounded-lg hover:bg-white/10 transition-colors"
                      >
                        Reset
                      </button>
                    </div>
                  </div>

                  {/* Impact Preview */}
                  <div className="bg-[#111] border border-white/10 rounded-lg p-4">
                    <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                      <Target size={18} className="text-[#FFB800]" />
                      Impact Preview
                    </h3>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-white/80">Affected Responses</span>
                        <span className="text-lg font-bold text-[#FFB800]">
                          {selectedMemory.affectedResponses}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-white/80">Current Shapley Value</span>
                        <span className="text-lg font-bold text-[#00D9FF]">
                          {(selectedMemory.shapleyValue * 100).toFixed(0)}%
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-white/80">Token Cost</span>
                        <span className="text-lg font-bold text-white">
                          {selectedMemory.tokenCost}t
                        </span>
                      </div>
                      {editContent !== selectedMemory.content && (
                        <div className="mt-4 p-3 bg-[#FFB800]/20 border border-[#FFB800]/40 rounded-lg">
                          <div className="text-sm text-[#FFB800] font-bold mb-1">
                            ⚠️ Changes Pending
                          </div>
                          <div className="text-xs text-white/80">
                            Saving will trigger re-ranking of {selectedMemory.affectedResponses} responses
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <div className="bg-[#111] border border-white/10 rounded-lg p-8 text-center">
                  <Info size={48} className="text-white/30 mx-auto mb-4" />
                  <div className="text-lg text-white/80">
                    Select a memory from the left to begin editing
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* OPTIMIZER MODE */}
        {mode === 'optimizer' && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Sliders size={20} className="text-[#00D9FF]" />
                A/B Testing Optimizer
              </h2>

              {/* Sliders */}
              <div className="space-y-6 mb-8">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-bold text-white">
                      Retrieval Top-K
                    </label>
                    <span className="text-lg font-bold text-[#00D9FF]">{kValue}</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="20"
                    value={kValue}
                    onChange={(e) => setKValue(parseInt(e.target.value))}
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="text-xs text-white/80 mt-1">
                    How many memories to retrieve per query
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-bold text-white">
                      Recency Weight
                    </label>
                    <span className="text-lg font-bold text-[#00D9FF]">{recencyWeight.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={recencyWeight}
                    onChange={(e) => setRecencyWeight(parseFloat(e.target.value))}
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="text-xs text-white/80 mt-1">
                    Bias toward newer memories (0 = pure relevance, 1 = pure recency)
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-sm font-bold text-white">
                      Safety Boost
                    </label>
                    <span className="text-lg font-bold text-[#00D9FF]">{safetyBoost.toFixed(1)}x</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    step="0.5"
                    value={safetyBoost}
                    onChange={(e) => setSafetyBoost(parseFloat(e.target.value))}
                    className="w-full h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
                  />
                  <div className="text-xs text-white/80 mt-1">
                    Multiplier for critical safety memories
                  </div>
                </div>
              </div>

              {/* A/B Test Results */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                  <h3 className="text-sm font-bold text-white/80 mb-4">CURRENT CONFIG</h3>
                  <div className="space-y-3">
                    <div>
                      <div className="text-xs text-white/80 mb-1">Accuracy</div>
                      <div className="text-2xl font-bold text-white">87.2%</div>
                    </div>
                    <div>
                      <div className="text-xs text-white/80 mb-1">Avg Token Cost</div>
                      <div className="text-2xl font-bold text-[#FFB800]">728t</div>
                    </div>
                    <div>
                      <div className="text-xs text-white/80 mb-1">Avg Latency</div>
                      <div className="text-2xl font-bold text-white/90">245ms</div>
                    </div>
                  </div>
                </div>

                <div className="bg-[#0A0A0A] border-2 border-[#00D9FF]/40 rounded-lg p-4">
                  <h3 className="text-sm font-bold text-[#00D9FF] mb-4">NEW CONFIG (PREDICTED)</h3>
                  <div className="space-y-3">
                    <div>
                      <div className="text-xs text-white/80 mb-1">Accuracy</div>
                      <div className="text-2xl font-bold text-green-400 flex items-center gap-2">
                        91.8%
                        <span className="text-sm">↑ 4.6%</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-white/80 mb-1">Avg Token Cost</div>
                      <div className="text-2xl font-bold text-[#FFB800] flex items-center gap-2">
                        {Math.round(728 * (kValue / 8))}t
                        <span className={`text-sm ${kValue < 8 ? 'text-green-400' : 'text-[#FF3A5E]'}`}>
                          {kValue < 8 ? '↓' : '↑'} {Math.abs(Math.round((kValue / 8 - 1) * 100))}%
                        </span>
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-white/80 mb-1">Avg Latency</div>
                      <div className="text-2xl font-bold text-white/90 flex items-center gap-2">
                        {Math.round(245 * (kValue / 8))}ms
                        <span className={`text-sm ${kValue < 8 ? 'text-green-400' : 'text-[#FF3A5E]'}`}>
                          {kValue < 8 ? '↓' : '↑'} {Math.abs(Math.round((kValue / 8 - 1) * 100))}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <button
                onClick={handleRunABTest}
                className="w-full mt-6 py-3 bg-[#00D9FF] text-black font-bold rounded-lg hover:bg-[#00D9FF]/80 transition-colors flex items-center gap-2 justify-center"
              >
                <PlayCircle size={18} />
                Run A/B Test (Shadow Traffic)
              </button>
            </div>
          </div>
        )}

        {/* RESOLVER MODE */}
        {mode === 'resolver' && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <GitBranch size={20} className="text-[#FF3A5E]" />
                Contradiction Resolver
              </h2>

              {/* Contradicting Memories */}
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-[#FF3A5E]/10 border-2 border-[#FF3A5E] rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm font-bold text-[#FF3A5E]">M001</span>
                    <span className="text-xs px-2 py-0.5 bg-[#FF3A5E]/20 border border-[#FF3A5E]/40 text-[#FF3A5E] rounded">
                      OLDER
                    </span>
                  </div>
                  <div className="text-sm text-white/90 mb-4">
                    Patient takes Warfarin 5mg daily
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-white/80">Created</span>
                      <span className="text-white">2025-11-12</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80">Shapley Value</span>
                      <span className="text-[#00D9FF] font-bold">82%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80">Affected Responses</span>
                      <span className="text-[#FFB800] font-bold">247</span>
                    </div>
                  </div>
                </div>

                <div className="bg-[#FF3A5E]/10 border-2 border-[#FF3A5E] rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm font-bold text-[#FF3A5E]">M089</span>
                    <span className="text-xs px-2 py-0.5 bg-green-500/20 border border-green-500/40 text-green-400 rounded">
                      NEWER
                    </span>
                  </div>
                  <div className="text-sm text-white/90 mb-4">
                    Patient switched to Eliquis 5mg after adverse reaction
                  </div>
                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-white/80">Created</span>
                      <span className="text-white">2026-01-15</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80">Shapley Value</span>
                      <span className="text-[#00D9FF] font-bold">8%</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-white/80">Affected Responses</span>
                      <span className="text-[#FFB800] font-bold">12</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Resolution Options */}
              <div className="space-y-3">
                <button
                  onClick={handleArchiveOlder}
                  disabled={isResolving}
                  className={`w-full py-3 bg-green-500/20 border border-green-500/40 text-green-400 rounded-lg font-bold transition-all flex items-center gap-2 justify-center ${
                    isResolving ? 'opacity-50 cursor-not-allowed' : 'hover:bg-green-500/30 hover:scale-105'
                  }`}
                >
                  {isResolving ? (
                    <RotateCcw size={18} className="animate-spin" />
                  ) : (
                    <CheckCircle size={18} />
                  )}
                  Archive M001 (Promote Newer Memory)
                </button>
                <button
                  onClick={handleMergeMemories}
                  disabled={isResolving}
                  className={`w-full py-3 bg-[#FFB800]/20 border border-[#FFB800]/40 text-[#FFB800] rounded-lg font-bold transition-all flex items-center gap-2 justify-center ${
                    isResolving ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#FFB800]/30 hover:scale-105'
                  }`}
                >
                  {isResolving ? (
                    <RotateCcw size={18} className="animate-spin" />
                  ) : (
                    <GitBranch size={18} />
                  )}
                  Merge into Single Timeline Memory
                </button>
                <button
                  onClick={handleKeepBoth}
                  disabled={isResolving}
                  className={`w-full py-3 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded-lg font-bold transition-all flex items-center gap-2 justify-center ${
                    isResolving ? 'opacity-50 cursor-not-allowed' : 'hover:bg-[#00D9FF]/30 hover:scale-105'
                  }`}
                >
                  {isResolving ? (
                    <RotateCcw size={18} className="animate-spin" />
                  ) : (
                    <Info size={18} />
                  )}
                  Keep Both (Add Temporal Context)
                </button>
                <button
                  onClick={() => setMode('overview')}
                  disabled={isResolving}
                  className={`w-full py-3 bg-white/5 border border-white/20 text-white/70 rounded-lg font-bold transition-all flex items-center gap-2 justify-center ${
                    isResolving ? 'opacity-50 cursor-not-allowed' : 'hover:bg-white/10 hover:scale-105'
                  }`}
                >
                  <XCircle size={18} />
                  Ignore (Manual Review Later)
                </button>
              </div>
            </div>
          </div>
        )}

        {/* BLAST RADIUS MODE */}
        {mode === 'blast' && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <h2 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
                <Target size={20} className="text-[#FFB800]" />
                Blast Radius Calculator
              </h2>

              <div className="mb-6">
                <label className="text-sm font-bold text-white mb-2 block">
                  Select Memory to Analyze
                </label>
                <select
                  value={selectedMemory?.id || ''}
                  onChange={(e) => {
                    const mem = memories.find(m => m.id === e.target.value);
                    setSelectedMemory(mem || null);
                  }}
                  className="w-full bg-[#0A0A0A] border border-white/20 rounded-lg p-3 text-white text-sm focus:outline-none focus:border-[#00D9FF]"
                >
                  <option value="">Choose a memory...</option>
                  {memories.map(m => (
                    <option key={m.id} value={m.id}>
                      {m.id} - {m.content.slice(0, 50)}...
                    </option>
                  ))}
                </select>
              </div>

              {selectedMemory && (
                <>
                  {/* Impact Metrics */}
                  <div className="grid grid-cols-4 gap-4 mb-6">
                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4 text-center">
                      <div className="text-xs text-white/80 mb-2">Affected Responses</div>
                      <div className="text-3xl font-bold text-[#FFB800]">
                        {selectedMemory.affectedResponses}
                      </div>
                    </div>
                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4 text-center">
                      <div className="text-xs text-white/80 mb-2">Shapley Impact</div>
                      <div className="text-3xl font-bold text-[#00D9FF]">
                        {(selectedMemory.shapleyValue * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4 text-center">
                      <div className="text-xs text-white/80 mb-2">Token Cost</div>
                      <div className="text-3xl font-bold text-white">
                        {selectedMemory.tokenCost}t
                      </div>
                    </div>
                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4 text-center">
                      <div className="text-xs text-white/80 mb-2">Confidence</div>
                      <div className="text-3xl font-bold text-green-400">
                        {(selectedMemory.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                  </div>

                  {/* What-If Scenarios */}
                  <div className="space-y-3">
                    <h3 className="text-lg font-bold text-white mb-3">What-If Analysis</h3>

                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-white">If Archived</span>
                        <span className="text-xs px-2 py-0.5 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded">
                          PREDICTION
                        </span>
                      </div>
                      <div className="text-sm text-white/80 mb-3">
                        {selectedMemory.affectedResponses} responses will need re-ranking
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-white/80">Accuracy Change:</span>
                          <span className="ml-2 text-[#FF3A5E] font-bold">
                            -{(selectedMemory.shapleyValue * 5).toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-white/80">Token Savings:</span>
                          <span className="ml-2 text-green-400 font-bold">
                            -{selectedMemory.tokenCost}t/query
                          </span>
                        </div>
                      </div>
                    </div>

                    <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-bold text-white">If Promoted to HOT</span>
                        <span className="text-xs px-2 py-0.5 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded">
                          PREDICTION
                        </span>
                      </div>
                      <div className="text-sm text-white/80 mb-3">
                        Will be retrieved more frequently in top-k results
                      </div>
                      <div className="grid grid-cols-2 gap-4 text-xs">
                        <div>
                          <span className="text-white/80">Accuracy Change:</span>
                          <span className="ml-2 text-green-400 font-bold">
                            +{(selectedMemory.shapleyValue * 2).toFixed(1)}%
                          </span>
                        </div>
                        <div>
                          <span className="text-white/80">Token Cost:</span>
                          <span className="ml-2 text-[#FFB800] font-bold">
                            +{Math.round(selectedMemory.tokenCost * 0.3)}t/query
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* AUDIT MODE */}
        {mode === 'audit' && (
          <div className="space-y-6 animate-fade-in">
            <div className="bg-[#111] border border-white/10 rounded-lg p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                  <Shield size={20} className="text-[#00D9FF]" />
                  Compliance Audit Trail
                </h2>
                <button
                  onClick={handleExportReport}
                  className="px-4 py-2 bg-[#00D9FF]/20 border border-[#00D9FF]/40 text-[#00D9FF] rounded-lg font-bold hover:bg-[#00D9FF]/30 transition-colors flex items-center gap-2"
                >
                  <Upload size={16} />
                  Export Report
                </button>
              </div>

              {/* Audit Log */}
              <div className="space-y-3">
                <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-[#FF3A5E]"></div>
                      <span className="text-sm font-bold text-white">Memory Edit</span>
                    </div>
                    <span className="text-xs text-white/80">2026-02-11 14:23:15</span>
                  </div>
                  <div className="text-sm text-white/90 mb-2">
                    <strong className="text-[#00D9FF]">admin@cortex.ai</strong> edited M001 content
                  </div>
                  <div className="text-xs text-white/80">
                    Affected: 247 responses | Action: Content modified
                  </div>
                </div>

                <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-[#FFB800]"></div>
                      <span className="text-sm font-bold text-white">Tier Change</span>
                    </div>
                    <span className="text-xs text-white/80">2026-02-11 10:15:42</span>
                  </div>
                  <div className="text-sm text-white/90 mb-2">
                    <strong className="text-[#00D9FF]">ops@cortex.ai</strong> moved M067 from HOT → WARM
                  </div>
                  <div className="text-xs text-white/80">
                    Reason: Shapley value below threshold | Auto-triggered
                  </div>
                </div>

                <div className="bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-[#00D9FF]"></div>
                      <span className="text-sm font-bold text-white">Memory Created</span>
                    </div>
                    <span className="text-xs text-white/80">2026-01-15 09:30:22</span>
                  </div>
                  <div className="text-sm text-white/90 mb-2">
                    <strong className="text-[#00D9FF]">system</strong> created M089 from follow-up visit
                  </div>
                  <div className="text-xs text-white/80">
                    Source: Healthcare agent auto-extraction | Confidence: 98%
                  </div>
                </div>

                <div className="bg-[#0A0A0A] border border-green-500/20 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-2 h-2 rounded-full bg-green-500"></div>
                      <span className="text-sm font-bold text-white">Contradiction Resolved</span>
                    </div>
                    <span className="text-xs text-white/80">2026-01-15 11:45:18</span>
                  </div>
                  <div className="text-sm text-white/90 mb-2">
                    <strong className="text-[#00D9FF]">admin@cortex.ai</strong> resolved M001 ↔ M089 conflict
                  </div>
                  <div className="text-xs text-white/80">
                    Action: Promoted M089, archived M001 | Blast radius: 247 responses updated
                  </div>
                </div>
              </div>

              {/* GDPR Compliance */}
              <div className="mt-6 bg-[#0A0A0A] border border-white/20 rounded-lg p-4">
                <h3 className="text-lg font-bold text-white mb-4">GDPR Compliance Status</h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-sm text-white/80 mb-1">Data Retention</div>
                    <div className="flex items-center gap-2">
                      <CheckCircle size={16} className="text-green-400" />
                      <span className="text-sm text-green-400 font-bold">Compliant</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-white/80 mb-1">Audit Trail</div>
                    <div className="flex items-center gap-2">
                      <CheckCircle size={16} className="text-green-400" />
                      <span className="text-sm text-green-400 font-bold">Complete</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-white/80 mb-1">User Attribution</div>
                    <div className="flex items-center gap-2">
                      <CheckCircle size={16} className="text-green-400" />
                      <span className="text-sm text-green-400 font-bold">Tracked</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-white/80 mb-1">Deletion Provenance</div>
                    <div className="flex items-center gap-2">
                      <CheckCircle size={16} className="text-green-400" />
                      <span className="text-sm text-green-400 font-bold">Verifiable</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
