import { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { ArrowRight, Play, Activity, Cpu, Server, Database } from 'lucide-react'

interface HeroProps {
  onOpenDemo: () => void
  onOpenEarlyAccess?: () => void
}

/* ═══════════════════════════════════════════════════════════════════════
   TYPES & CONSTANTS
   ═══════════════════════════════════════════════════════════════════════ */

type FlowState = 'idle' | 'pruning' | 'gating'

const CYCLE_MS = 3400
const EASE: [number, number, number, number] = [0.22, 1, 0.36, 1]

/* ── Flow Node ──────────────────────────────────────────────────────── */

function FlowNode({
  label,
  icon: Icon,
  active,
  alert,
  glow,
}: {
  label: string
  icon: typeof Cpu
  active?: boolean
  alert?: boolean
  glow?: boolean
}) {
  return (
    <motion.div
      className="relative flex flex-col items-center gap-1.5"
      animate={
        glow
          ? {
              filter: [
                'drop-shadow(0 0 0px rgba(198,239,0,0))',
                'drop-shadow(0 0 16px rgba(198,239,0,0.5))',
                'drop-shadow(0 0 0px rgba(198,239,0,0))',
              ],
            }
          : { filter: 'drop-shadow(0 0 0px rgba(0,0,0,0))' }
      }
      transition={glow ? { duration: 1, ease: 'easeInOut' } : { duration: 0.3 }}
    >
      <div
        className={`w-[52px] h-[52px] rounded-xl bg-zinc-900 flex items-center justify-center shadow-[inset_0_2px_4px_rgba(0,0,0,0.5)] transition-colors duration-300 border ${
          alert
            ? 'border-red-500/60'
            : active
              ? 'border-[#c6ef00]/40'
              : 'border-zinc-700'
        }`}
      >
        <Icon
          size={18}
          strokeWidth={1.6}
          className={`transition-colors duration-300 ${
            alert
              ? 'text-red-400'
              : active
                ? 'text-[#c6ef00]'
                : 'text-zinc-400'
          }`}
        />
      </div>
      <span className="text-[10px] font-bold text-zinc-500 tracking-tight" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
        {label}
      </span>
    </motion.div>
  )
}

/* ── SVG Dashed Connector ───────────────────────────────────────────── */

function Connector({ from, to }: { from: string; to: string }) {
  return (
    <svg
      className="absolute top-[26px] h-[2px] pointer-events-none z-0"
      style={{ left: from, width: to }}
      preserveAspectRatio="none"
    >
      <line
        x1="0"
        y1="1"
        x2="100%"
        y2="1"
        stroke="#3f3f46"
        strokeWidth="1.5"
        strokeDasharray="5 4"
      />
    </svg>
  )
}

/* ── Glow Particle ──────────────────────────────────────────────────── */

function GlowParticle({
  from,
  to,
  color,
  glowColor,
  size = 8,
  delay = 0,
  duration = 1.1,
  onComplete,
}: {
  from: number
  to: number
  color: string
  glowColor?: string
  size?: number
  delay?: number
  duration?: number
  onComplete?: () => void
}) {
  const glow = glowColor || color
  return (
    <motion.div
      className="absolute rounded-full"
      style={{
        width: size,
        height: size,
        top: 26 - size / 2,
        backgroundColor: color,
        boxShadow: `0 0 ${size + 4}px ${glow}, 0 0 ${size * 3}px ${glow}50`,
      }}
      initial={{ left: `${from}%`, opacity: 0, scale: 0.3 }}
      animate={{
        left: `${to}%`,
        opacity: [0, 1, 1, 0.4],
        scale: [0.3, 1, 1, 0.7],
      }}
      exit={{ opacity: 0, scale: 0 }}
      transition={{ duration, delay, ease: EASE }}
      onAnimationComplete={onComplete}
    />
  )
}

/* ── Memory Cluster (for pruning state) ─────────────────────────────── */

function MemoryCluster({
  from,
  to,
  delay = 0,
  duration = 1,
  onComplete,
}: {
  from: number
  to: number
  delay?: number
  duration?: number
  onComplete?: () => void
}) {
  const dots = [
    { y: -6, size: 5 },
    { y: 3, size: 7 },
    { y: -2, size: 6 },
    { y: 5, size: 5 },
    { y: 0, size: 8 },
  ]
  return (
    <>
      {dots.map((d, i) => (
        <motion.div
          key={i}
          className="absolute rounded-full"
          style={{
            width: d.size,
            height: d.size,
            top: 26 + d.y - d.size / 2,
            backgroundColor: '#52525b',
            boxShadow: '0 0 6px rgba(82,82,91,0.4)',
          }}
          initial={{ left: `${from}%`, opacity: 0, scale: 0.2 }}
          animate={{
            left: `${to}%`,
            opacity: [0, 0.7, 0.7, 0],
            scale: [0.2, 1, 1, 0],
          }}
          transition={{
            duration,
            delay: delay + i * 0.04,
            ease: EASE,
          }}
          onAnimationComplete={i === 0 ? onComplete : undefined}
        />
      ))}
    </>
  )
}

/* ── Red Ripple (for gating state) ──────────────────────────────────── */

function Ripple() {
  return (
    <motion.div
      className="absolute rounded-xl pointer-events-none z-0"
      style={{
        top: -8,
        left: -8,
        right: -8,
        bottom: -8,
        border: '2px solid rgba(239,68,68,0.5)',
      }}
      initial={{ opacity: 0.7, scale: 1 }}
      animate={{ opacity: 0, scale: 1.5 }}
      transition={{ duration: 0.7, ease: 'easeOut' }}
    />
  )
}

/* ── Status Badge ───────────────────────────────────────────────────── */

function Badge({
  text,
  variant,
  position,
}: {
  text: string
  variant: 'lime' | 'red'
  position: 'above' | 'below'
}) {
  return (
    <motion.div
      className={`absolute left-1/2 -translate-x-1/2 z-20 ${
        position === 'above' ? '-top-8' : '-bottom-8'
      }`}
      initial={{ opacity: 0, y: position === 'above' ? 4 : -4, scale: 0.9 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: position === 'above' ? 4 : -4, scale: 0.9 }}
      transition={{ duration: 0.25 }}
    >
      <span
        className={`text-[9px] font-bold tracking-wide uppercase whitespace-nowrap px-2.5 py-1 rounded-full border ${
          variant === 'red'
            ? 'bg-red-500/10 text-red-500 border-red-500/30'
            : 'bg-[#536600]/30 text-[#c6ef00] border-[#536600]'
        }`}
        style={{ fontFamily: "'Space Grotesk', sans-serif" }}
      >
        {text}
      </span>
    </motion.div>
  )
}

/* ── Flow Animations per State ──────────────────────────────────────── */

function IdleFlow({ cycle }: { cycle: number }) {
  return (
    <div key={`idle-${cycle}`}>
      <GlowParticle from={12} to={50} color="#c6ef00" glowColor="#c6ef00" duration={1} />
      <GlowParticle from={50} to={88} color="#c6ef00" glowColor="#c6ef00" delay={1} duration={1} />
      <GlowParticle from={88} to={50} color="#52525b" delay={0.3} duration={1} />
      <GlowParticle from={50} to={12} color="#52525b" delay={1.3} duration={1} />
    </div>
  )
}

function PruningFlow({
  cycle,
  onCompress,
}: {
  cycle: number
  onCompress: () => void
}) {
  return (
    <div key={`prune-${cycle}`}>
      <GlowParticle from={12} to={50} color="#c6ef00" glowColor="#c6ef00" duration={1} />
      <GlowParticle from={50} to={88} color="#c6ef00" glowColor="#c6ef00" delay={1} duration={1} />
      <MemoryCluster from={88} to={50} delay={0.2} duration={1.1} onComplete={onCompress} />
      <GlowParticle
        from={50}
        to={12}
        color="#c6ef00"
        glowColor="#c6ef00"
        size={10}
        delay={1.5}
        duration={1}
      />
    </div>
  )
}

function GatingFlow({
  cycle,
  onBlock,
}: {
  cycle: number
  onBlock: () => void
}) {
  return (
    <div key={`gate-${cycle}`}>
      <GlowParticle from={12} to={50} color="#c6ef00" glowColor="#c6ef00" duration={1} />
      <GlowParticle from={50} to={88} color="#c6ef00" glowColor="#c6ef00" delay={1} duration={1} />
      <GlowParticle
        from={88}
        to={50}
        color="#ef4444"
        glowColor="#ef4444"
        size={10}
        delay={0.3}
        duration={1}
        onComplete={onBlock}
      />
      <GlowParticle from={50} to={12} color="#52525b" delay={1.8} duration={1} />
    </div>
  )
}

/* ── Segmented Control ──────────────────────────────────────────────── */

const tabs: { key: FlowState; label: string }[] = [
  { key: 'idle', label: 'Standard' },
  { key: 'pruning', label: 'Pruning' },
  { key: 'gating', label: 'Gating' },
]

function SegmentedControl({
  value,
  onChange,
}: {
  value: FlowState
  onChange: (s: FlowState) => void
}) {
  return (
    <div className="flex justify-center">
      <div className="inline-flex bg-zinc-900 border border-zinc-800 rounded-full p-1 gap-0.5 relative">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => onChange(tab.key)}
            className="relative z-10 px-3.5 py-1 rounded-full text-[11px] font-bold tracking-tight transition-colors duration-300"
            style={{
              color: value === tab.key ? '#0a0a0a' : '#71717a',
              fontFamily: "'Space Grotesk', sans-serif",
            }}
          >
            {value === tab.key && (
              <motion.div
                layoutId="segmented-pill"
                className="absolute inset-0 rounded-full bg-[#c6ef00]"
                style={{ zIndex: -1 }}
                transition={{ type: 'spring', stiffness: 400, damping: 30 }}
              />
            )}
            {tab.label}
          </button>
        ))}
      </div>
    </div>
  )
}

/* ── Command Center Card ────────────────────────────────────────────── */

function CommandCenter() {
  const [state, setState] = useState<FlowState>('pruning')
  const [cycle, setCycle] = useState(0)
  const [cortexa, setCortexa] = useState({
    active: false,
    alert: false,
    glow: false,
    badge: null as {
      text: string
      variant: 'lime' | 'red'
      position: 'above' | 'below'
    } | null,
  })

  const reset = useCallback(() => {
    setCortexa({ active: false, alert: false, glow: false, badge: null })
  }, [])

  useEffect(() => {
    reset()
    const iv = setInterval(() => {
      reset()
      setCycle((c) => c + 1)
    }, CYCLE_MS)
    return () => clearInterval(iv)
  }, [state, reset])

  const handleCompress = useCallback(() => {
    setCortexa({
      active: true,
      alert: false,
      glow: true,
      badge: {
        text: '-35% Tokens Compressed',
        variant: 'lime',
        position: 'above',
      },
    })
  }, [])

  const handleBlock = useCallback(() => {
    setCortexa({
      active: false,
      alert: true,
      glow: false,
      badge: {
        text: 'Toxic Vector Dropped',
        variant: 'red',
        position: 'below',
      },
    })
  }, [])

  return (
    <div className="bg-zinc-950/50 backdrop-blur-md border border-zinc-800 rounded-[2rem] shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] p-5 lg:p-6 space-y-5">
      <SegmentedControl
        value={state}
        onChange={(s) => {
          setState(s)
          setCycle(0)
          reset()
        }}
      />

      <div className="relative px-2" style={{ height: 94 }}>
        <Connector from="16%" to="24%" />
        <Connector from="60%" to="24%" />

        <div className="relative flex items-start justify-between z-10">
          <div style={{ width: '28%' }} className="flex justify-center">
            <FlowNode label="AI Agent" icon={Cpu} />
          </div>
          <div style={{ width: '28%' }} className="flex justify-center">
            <div className="relative">
              <FlowNode
                label="Cortexa"
                icon={Server}
                active={cortexa.active}
                alert={cortexa.alert}
                glow={cortexa.glow}
              />
              <AnimatePresence>
                {cortexa.alert && <Ripple />}
              </AnimatePresence>
              <AnimatePresence>
                {cortexa.badge && (
                  <Badge
                    text={cortexa.badge.text}
                    variant={cortexa.badge.variant}
                    position={cortexa.badge.position}
                  />
                )}
              </AnimatePresence>
            </div>
          </div>
          <div style={{ width: '28%' }} className="flex justify-center">
            <FlowNode label="Vector DB" icon={Database} />
          </div>
        </div>

        <div className="absolute inset-x-2 top-0 bottom-0 pointer-events-none overflow-hidden z-[5]">
          <AnimatePresence mode="wait">
            {state === 'idle' && <IdleFlow cycle={cycle} />}
            {state === 'pruning' && (
              <PruningFlow cycle={cycle} onCompress={handleCompress} />
            )}
            {state === 'gating' && (
              <GatingFlow cycle={cycle} onBlock={handleBlock} />
            )}
          </AnimatePresence>
        </div>
      </div>

      <div className="flex justify-center gap-5 pt-2 border-t border-zinc-800/60">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-[#c6ef00] shadow-[0_0_6px_#c6ef00]" />
          <span className="text-[10px] text-zinc-500">Prompt</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-zinc-600" />
          <span className="text-[10px] text-zinc-500">Memory</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 rounded-full bg-red-500 shadow-[0_0_6px_#ef4444]" />
          <span className="text-[10px] text-zinc-500">Blocked</span>
        </div>
      </div>
    </div>
  )
}

/* ═══════════════════════════════════════════════════════════════════════
   HERO SECTION — Dark Mode
   ═══════════════════════════════════════════════════════════════════════ */

export function Hero({ onOpenDemo, onOpenEarlyAccess }: HeroProps) {
  return (
    <section
      id="hero"
      data-theme="dark"
      className="relative min-h-[calc(100dvh-5rem)] flex items-center bg-zinc-900 overflow-hidden"
    >
      {/* Subtle radial gradient backdrop */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(198,239,0,0.06),transparent)] pointer-events-none" />

      <div className="relative z-10 max-w-screen-2xl mx-auto px-8 pt-20 w-full">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-14 items-center">
          {/* Left Column: Copy & CTAs */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.8,
              ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
            }}
            className="lg:col-span-7 space-y-6"
          >
            <div className="space-y-5">
              {/* Pill badge */}
              <motion.span
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.2 }}
                className="inline-flex items-center gap-2 bg-zinc-800/60 border border-zinc-700/50 text-zinc-300 px-4 py-1.5 rounded-full text-[10px] font-bold tracking-widest uppercase backdrop-blur-sm"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#c6ef00] animate-pulse" />
                Early Access — Now Open
              </motion.span>

              {/* Headline */}
              <h1
                className="text-5xl lg:text-7xl xl:text-8xl font-bold leading-[0.9] tracking-tighter text-zinc-50"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              >
                Your agent{' '}
                <span className="relative inline-block transform -rotate-1 px-3">
                  <span className="absolute inset-0 bg-[#c6ef00] rounded-sm -z-10" />
                  <span className="text-zinc-950">hallucinated.</span>
                </span>{' '}
                <br />
                <span className="italic font-light text-zinc-400">
                  Which memory
                </span>{' '}
                caused it?
              </h1>
            </div>

            {/* Subtext */}
            <p className="text-base lg:text-lg text-zinc-400 max-w-xl leading-relaxed">
              Cortexa traces every LLM response back to the memory fragments
              that shaped it. Find the root cause in seconds. Fix it before your users notice.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap gap-3 pt-1">
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })}
                className="bg-[#c6ef00] text-zinc-950 px-7 py-3.5 rounded-full font-bold tracking-tight hover:bg-[#d4f533] transition-colors flex items-center gap-2.5 shadow-[0_0_20px_rgba(198,239,0,0.15)] text-sm"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              >
                See How It Works
                <ArrowRight size={16} />
              </motion.button>
              <motion.button
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.97 }}
                onClick={onOpenDemo}
                className="bg-zinc-800 text-zinc-50 px-7 py-3.5 rounded-full font-bold tracking-tight border border-zinc-700 hover:bg-zinc-700 transition-colors flex items-center gap-2 text-sm"
                style={{ fontFamily: "'Space Grotesk', sans-serif" }}
              >
                <Play size={16} fill="currentColor" className="text-[#c6ef00]" />
                Watch Demo
              </motion.button>
            </div>
          </motion.div>

          {/* Right Column: Command Center */}
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{
              duration: 0.8,
              delay: 0.3,
              ease: [0.16, 1, 0.3, 1] as [number, number, number, number],
            }}
            className="lg:col-span-5"
          >
            <CommandCenter />
          </motion.div>
        </div>
      </div>
    </section>
  )
}
