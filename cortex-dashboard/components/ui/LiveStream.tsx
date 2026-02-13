'use client'

import { useState, useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Clock, Zap } from 'lucide-react'
import { format } from 'date-fns'

interface AttributionEvent {
  id: string
  query: string
  memories: Array<{
    id: string
    score: number
    agent: string
  }>
  timestamp: Date
  method: 'shapley' | 'contextcite'
  computeTime: number
  confidence: number
}

interface LiveStreamProps {
  maxItems?: number
  autoScroll?: boolean
}

// Mock data generator
function generateMockEvent(): AttributionEvent {
  const queries = [
    "What's our Q4 revenue forecast?",
    "List all employees in engineering",
    "Show me the compliance audit trail",
    "What were last month's support tickets?",
    "Explain the attribution scoring algorithm",
    "Which memories are most frequently used?"
  ]

  const agents = ['legal-001', 'finance-012', 'hr-003', 'sales-045', 'support-089']

  const numMemories = Math.floor(Math.random() * 4) + 2 // 2-5 memories

  return {
    id: `evt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
    query: queries[Math.floor(Math.random() * queries.length)],
    memories: Array.from({ length: numMemories }, (_, i) => ({
      id: `mem_${Math.floor(Math.random() * 10000).toString().padStart(4, '0')}`,
      score: parseFloat((Math.random() * 0.8 + 0.1).toFixed(2)),
      agent: agents[Math.floor(Math.random() * agents.length)]
    })).sort((a, b) => b.score - a.score),
    timestamp: new Date(),
    method: Math.random() > 0.3 ? 'contextcite' : 'shapley',
    computeTime: Math.random() > 0.3 ? Math.floor(Math.random() * 12) + 5 : Math.floor(Math.random() * 4000) + 1000,
    confidence: parseFloat((Math.random() * 0.15 + 0.82).toFixed(2))
  }
}

export default function LiveStream({ maxItems = 10, autoScroll = true }: LiveStreamProps) {
  const [events, setEvents] = useState<AttributionEvent[]>([])
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // Initial events
    setEvents(Array.from({ length: 3 }, generateMockEvent))

    // Add new event every 3-8 seconds
    const interval = setInterval(() => {
      setEvents(prev => {
        const newEvents = [generateMockEvent(), ...prev]
        return newEvents.slice(0, maxItems)
      })
    }, Math.random() * 5000 + 3000)

    return () => clearInterval(interval)
  }, [maxItems])

  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = 0
    }
  }, [events, autoScroll])

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="relative">
            <div className="w-2 h-2 bg-success rounded-full animate-pulse-glow" />
            <div className="absolute inset-0 w-2 h-2 bg-success rounded-full animate-ping" />
          </div>
          <h3 className="text-sm font-semibold text-foreground/80 uppercase tracking-wide">
            Live Attribution Stream
          </h3>
        </div>
        <div className="text-xs text-foreground/40 font-mono">
          {events.length} events
        </div>
      </div>

      {/* Stream */}
      <div
        ref={containerRef}
        className="space-y-2 max-h-[600px] overflow-y-auto pr-2 scroll-smooth"
      >
        <AnimatePresence mode="popLayout">
          {events.map((event, index) => (
            <motion.div
              key={event.id}
              initial={{ opacity: 0, height: 0, marginBottom: 0 }}
              animate={{
                opacity: 1,
                height: 'auto',
                marginBottom: index === events.length - 1 ? 0 : 8
              }}
              exit={{ opacity: 0, height: 0, marginBottom: 0 }}
              transition={{ duration: 0.3 }}
            >
              <div className="glass rounded-lg p-3 border border-border/50 hover:border-border transition-all">
                {/* Query */}
                <div className="flex items-start gap-2 mb-2">
                  <Brain className="w-4 h-4 text-engine-1 mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-foreground/90 font-medium line-clamp-1">
                      {event.query}
                    </p>
                    <div className="flex items-center gap-3 mt-1 text-xs text-foreground/50 font-mono">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {format(event.timestamp, 'HH:mm:ss')}
                      </span>
                      <span className="flex items-center gap-1">
                        <Zap className="w-3 h-3" />
                        {event.computeTime}ms
                      </span>
                      <span className={`
                        px-1.5 py-0.5 rounded text-[10px] font-semibold uppercase
                        ${event.method === 'shapley' ? 'bg-engine-1/20 text-engine-1' : 'bg-engine-4/20 text-engine-4'}
                      `}>
                        {event.method}
                      </span>
                      <span className={`
                        px-1.5 py-0.5 rounded text-[10px] font-semibold
                        ${event.confidence >= 0.9 ? 'bg-success/20 text-success' :
                          event.confidence >= 0.8 ? 'bg-warning/20 text-warning' :
                          'bg-critical/20 text-critical'}
                      `}>
                        LDS {event.confidence}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Memories */}
                <div className="pl-6 space-y-1">
                  {event.memories.map((memory, idx) => (
                    <motion.div
                      key={memory.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: idx * 0.05 }}
                      className="flex items-center gap-2 text-xs"
                    >
                      <div className="w-1 h-3 rounded-full" style={{
                        width: `${Math.max(memory.score * 32, 2)}px`,
                        backgroundColor: `hsl(${200 + memory.score * 80}, 70%, 50%)`
                      }} />
                      <span className="font-mono text-foreground/60">{memory.id}</span>
                      <span className="text-foreground/80 font-semibold font-mono">
                        {memory.score.toFixed(2)}
                      </span>
                      <span className="text-foreground/40">({memory.agent})</span>
                    </motion.div>
                  ))}
                </div>
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}
