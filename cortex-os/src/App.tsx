import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Brain,
  Search,
  Shield,
  Zap,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Clock,
  DollarSign,
  TrendingUp,
  Eye,
  FileCheck,
  ChevronDown,
  Terminal,
  Activity,

  Trash2,
  ExternalLink,
  Layers,
} from 'lucide-react'

// ─── Hooks ──────────────────────────────────────────────────────────────────

function useInView(threshold = 0.2) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true)
          observer.unobserve(el)
        }
      },
      { threshold }
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [threshold])

  return { ref, inView }
}

function useStaggeredReveal(inView: boolean, steps: number, intervalMs = 400) {
  const [visibleStep, setVisibleStep] = useState(0)

  useEffect(() => {
    if (!inView) return
    if (visibleStep >= steps) return
    const timer = setTimeout(() => setVisibleStep((s) => s + 1), intervalMs)
    return () => clearTimeout(timer)
  }, [inView, visibleStep, steps, intervalMs])

  return visibleStep
}

// ─── Reusable Components ────────────────────────────────────────────────────

function Badge({ children, variant = 'default' }: { children: React.ReactNode; variant?: 'default' | 'red' | 'green' | 'yellow' }) {
  const colors = {
    default: 'bg-zinc-800 text-zinc-300 border-zinc-700',
    red: 'bg-red-950/50 text-red-400 border-red-800/50',
    green: 'bg-emerald-950/50 text-emerald-400 border-emerald-800/50',
    yellow: 'bg-yellow-950/50 text-yellow-400 border-yellow-800/50',
  }
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono rounded border ${colors[variant]}`}>
      {children}
    </span>
  )
}

function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`bg-zinc-900/80 border border-zinc-800 rounded-lg backdrop-blur-sm ${className}`}>
      {children}
    </div>
  )
}

function Button({
  children,
  variant = 'primary',
  onClick,
  className = '',
}: {
  children: React.ReactNode
  variant?: 'primary' | 'secondary' | 'ghost'
  onClick?: () => void
  className?: string
}) {
  const styles = {
    primary: 'bg-emerald-600 hover:bg-emerald-500 text-white border-emerald-500',
    secondary: 'bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border-zinc-700',
    ghost: 'bg-transparent hover:bg-zinc-800/50 text-zinc-400 hover:text-zinc-200 border-transparent',
  }
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-5 py-2.5 text-sm font-medium rounded-lg border transition-all duration-200 ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-4">
      <div className="h-px w-8 bg-emerald-500/50" />
      <span className="text-xs font-mono text-emerald-500 uppercase tracking-widest">{children}</span>
      <div className="h-px flex-1 bg-emerald-500/10" />
    </div>
  )
}

// ─── Section 1: Hero ────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center px-6">
      {/* Background grid */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(16,185,129,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(16,185,129,0.3) 1px, transparent 1px)',
          backgroundSize: '60px 60px',
        }}
      />

      <div className="relative max-w-4xl mx-auto text-center">
        {/* Logo/brand */}
        <div className="flex items-center justify-center gap-3 mb-8 animate-fade-in-up opacity-0-initial">
          <Brain className="w-8 h-8 text-emerald-500" />
          <span className="text-xl font-mono font-bold tracking-tight text-white">
            CORTEXA
          </span>
        </div>

        {/* Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-bold leading-tight text-white mb-6 animate-fade-in-up opacity-0-initial stagger-1">
          Your agent hallucinated.
          <br />
          <span className="text-emerald-400">Which memory caused it?</span>
        </h1>

        {/* Subline */}
        <p className="text-lg sm:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 animate-fade-in-up opacity-0-initial stagger-2">
          Cortexa traces every LLM response back to the memories that influenced it.
          Find the root cause in seconds, not hours. Fix it before your users notice.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up opacity-0-initial stagger-3">
          <Button
            variant="primary"
            onClick={() =>
              document.getElementById('trace-demo')?.scrollIntoView({ behavior: 'smooth' })
            }
          >
            See How It Works
            <ArrowRight className="w-4 h-4" />
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              document.getElementById('manifesto')?.scrollIntoView({ behavior: 'smooth' })
            }
          >
            Read the Manifesto
          </Button>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <ChevronDown className="w-5 h-5 text-zinc-600" />
        </div>
      </div>
    </section>
  )
}

// ─── Section 2: Hallucination Trace Demo ────────────────────────────────────

function TraceDemo() {
  const { ref, inView } = useInView(0.15)
  const step = useStaggeredReveal(inView, 8, 500)

  return (
    <section id="trace-demo" className="py-24 px-6" ref={ref}>
      <div className="max-w-4xl mx-auto">
        <SectionLabel>Live Trace</SectionLabel>
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          Watch a hallucination get traced in real time
        </h2>
        <p className="text-zinc-400 mb-12 max-w-2xl">
          An agent responds to a customer. The answer is wrong. Cortexa shows you exactly
          which memory caused it, why it was selected, and how to fix it.
        </p>

        <Card className="p-0 overflow-hidden">
          {/* Terminal header */}
          <div className="flex items-center gap-2 px-4 py-3 bg-zinc-950 border-b border-zinc-800">
            <div className="flex gap-1.5">
              <div className="w-3 h-3 rounded-full bg-red-500/80" />
              <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
              <div className="w-3 h-3 rounded-full bg-green-500/80" />
            </div>
            <span className="text-xs font-mono text-zinc-500 ml-2">cortexa trace --query "subscription status"</span>
          </div>

          <div className="p-6 sm:p-8 space-y-0 font-mono text-sm">
            {/* Step 1: Agent response */}
            {step >= 1 && (
              <div className="animate-fade-in-up opacity-0-initial mb-6">
                <div className="text-zinc-500 text-xs mb-2">AGENT RESPONSE</div>
                <div className="bg-zinc-950 rounded-lg p-4 border border-zinc-800">
                  <p className="text-zinc-200">
                    "Your subscription renews on <span className="text-red-400 font-semibold underline decoration-red-400/50">March 15th</span>."
                  </p>
                </div>
              </div>
            )}

            {/* Step 2: Ground truth */}
            {step >= 2 && (
              <div className="animate-fade-in-up opacity-0-initial mb-6">
                <div className="flex items-center gap-2 text-xs mb-2">
                  <XCircle className="w-3.5 h-3.5 text-red-400" />
                  <span className="text-red-400">GROUND TRUTH MISMATCH</span>
                </div>
                <div className="bg-red-950/20 rounded-lg p-4 border border-red-800/30">
                  <p className="text-red-300">
                    User cancelled their subscription on February 1st.
                  </p>
                </div>
              </div>
            )}

            {/* Step 3: Trace header */}
            {step >= 3 && (
              <div className="animate-fade-in-up opacity-0-initial mb-4">
                <div className="flex items-center gap-2 text-xs text-zinc-500 mb-3 pt-2 border-t border-zinc-800">
                  <Search className="w-3.5 h-3.5" />
                  ATTRIBUTION TRACE — 4 memories retrieved, 2 causal
                </div>
              </div>
            )}

            {/* Step 4: Memory #47 (stale, high attribution) */}
            {step >= 4 && (
              <div className="animate-slide-in-left opacity-0-initial mb-3">
                <div className="bg-red-950/10 rounded-lg p-4 border border-red-800/30 animate-pulse-glow">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-400">→</span>
                      <span className="text-zinc-300">Memory #47</span>
                      <Badge variant="red">attribution: 0.73</Badge>
                    </div>
                    <Badge variant="red">
                      <AlertTriangle className="w-3 h-3" />
                      STALE
                    </Badge>
                  </div>
                  <p className="text-zinc-400 text-xs ml-5 mb-1">
                    "User subscription renews monthly on the 15th"
                  </p>
                  <p className="text-red-400/70 text-xs ml-5">
                    <Clock className="w-3 h-3 inline mr-1" />
                    Last verified: 4 months ago — no recency check applied
                  </p>
                </div>
              </div>
            )}

            {/* Step 5: Memory #198 (current but buried) */}
            {step >= 5 && (
              <div className="animate-slide-in-left opacity-0-initial mb-4">
                <div className="bg-emerald-950/10 rounded-lg p-4 border border-emerald-800/30">
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-zinc-400">→</span>
                      <span className="text-zinc-300">Memory #198</span>
                      <Badge variant="green">attribution: 0.12</Badge>
                    </div>
                    <Badge variant="green">
                      <CheckCircle className="w-3 h-3" />
                      CURRENT
                    </Badge>
                  </div>
                  <p className="text-zinc-400 text-xs ml-5 mb-1">
                    "User cancelled subscription Feb 1"
                  </p>
                  <p className="text-yellow-400/70 text-xs ml-5">
                    <AlertTriangle className="w-3 h-3 inline mr-1" />
                    Retrieval rank: 4th — correct memory was buried
                  </p>
                </div>
              </div>
            )}

            {/* Step 6: Diagnosis */}
            {step >= 6 && (
              <div className="animate-fade-in-up opacity-0-initial mb-4 pt-3 border-t border-zinc-800">
                <div className="bg-zinc-950 rounded-lg p-4 border border-yellow-800/30">
                  <div className="flex items-center gap-2 text-yellow-400 text-xs mb-2">
                    <Eye className="w-3.5 h-3.5" />
                    DIAGNOSIS
                  </div>
                  <p className="text-zinc-200 text-sm">
                    Stale memory outranked current memory. Memory #47 has not been verified
                    in 4 months and contains outdated subscription data. The correct information
                    (Memory #198) was retrieved but ranked 4th due to embedding similarity
                    favoring the older, more detailed entry.
                  </p>
                </div>
              </div>
            )}

            {/* Step 7: Fix */}
            {step >= 7 && (
              <div className="animate-fade-in-up opacity-0-initial mb-4">
                <div className="bg-emerald-950/20 rounded-lg p-4 border border-emerald-800/30 animate-pulse-glow-green">
                  <div className="flex items-center gap-2 text-emerald-400 text-xs mb-2">
                    <Zap className="w-3.5 h-3.5" />
                    RECOMMENDED FIX
                  </div>
                  <ul className="text-zinc-300 text-sm space-y-1">
                    <li>→ Invalidate Memory #47 (stale, contradicted)</li>
                    <li>→ Boost recency weight in retrieval scoring</li>
                    <li>→ Flag 3 similar stale memories for review</li>
                  </ul>
                </div>
              </div>
            )}

            {/* Step 8: Time saved */}
            {step >= 8 && (
              <div className="animate-fade-in-up opacity-0-initial">
                <div className="flex items-center justify-between pt-3 border-t border-zinc-800">
                  <div className="flex items-center gap-2">
                    <Activity className="w-4 h-4 text-emerald-500" />
                    <span className="text-emerald-400">Time to root cause: <strong>3 seconds</strong></span>
                  </div>
                  <span className="text-zinc-600 text-xs">previously: ~45 minutes of manual debugging</span>
                </div>
              </div>
            )}
          </div>
        </Card>
      </div>
    </section>
  )
}

// ─── Section 3: Three Questions ─────────────────────────────────────────────

function ThreeQuestions() {
  const { ref, inView } = useInView(0.1)

  return (
    <section className="py-24 px-6" ref={ref}>
      <div className="max-w-6xl mx-auto">
        <SectionLabel>The Blind Spots</SectionLabel>
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          Three questions you can't answer today
        </h2>
        <p className="text-zinc-400 mb-12 max-w-2xl">
          You're running thousands of queries through memories every day.
          But can you answer these?
        </p>

        <div className="grid md:grid-cols-3 gap-6">
          {/* Card 1: Memory P&L */}
          <Card className={`p-6 transition-all duration-700 ${inView ? 'animate-fade-in-up' : 'opacity-0'}`}>
            <div className="flex items-center gap-2 mb-4">
              <DollarSign className="w-5 h-5 text-emerald-500" />
              <h3 className="text-lg font-semibold text-white">
                Which memories are worth paying for?
              </h3>
            </div>

            {/* Mini P&L table */}
            <div className="font-mono text-xs mb-4">
              <div className="grid grid-cols-4 gap-2 pb-2 mb-2 border-b border-zinc-800 text-zinc-500">
                <span>MEMORY</span>
                <span className="text-right">COST/D</span>
                <span className="text-right">ATTR</span>
                <span className="text-right">ROI</span>
              </div>
              <div className="grid grid-cols-4 gap-2 py-1.5 text-zinc-300">
                <span className="truncate">user_prefs</span>
                <span className="text-right">$0.42</span>
                <span className="text-right text-emerald-400">0.89</span>
                <span className="text-right text-emerald-400">+312%</span>
              </div>
              <div className="grid grid-cols-4 gap-2 py-1.5 text-zinc-300">
                <span className="truncate">past_orders</span>
                <span className="text-right">$1.20</span>
                <span className="text-right text-emerald-400">0.67</span>
                <span className="text-right text-emerald-400">+89%</span>
              </div>
              <div className="grid grid-cols-4 gap-2 py-1.5 bg-red-950/20 -mx-2 px-2 rounded text-zinc-300">
                <span className="truncate text-red-400">old_convos</span>
                <span className="text-right">$3.80</span>
                <span className="text-right text-red-400">0.03</span>
                <span className="text-right text-red-400">-94%</span>
              </div>
              <div className="grid grid-cols-4 gap-2 py-1.5 bg-red-950/20 -mx-2 px-2 rounded text-zinc-300">
                <span className="truncate text-red-400">raw_logs</span>
                <span className="text-right">$2.10</span>
                <span className="text-right text-red-400">0.01</span>
                <span className="text-right text-red-400">-98%</span>
              </div>
            </div>

            <div className="bg-zinc-950 rounded p-3 text-xs">
              <span className="text-zinc-400">
                <strong className="text-emerald-400">23 memories</strong> have negative ROI.
                Archiving them saves <strong className="text-emerald-400">$285/mo</strong>.
              </span>
            </div>
          </Card>

          {/* Card 2: Health */}
          <Card className={`p-6 transition-all duration-700 delay-150 ${inView ? 'animate-fade-in-up' : 'opacity-0'}`}>
            <div className="flex items-center gap-2 mb-4">
              <Activity className="w-5 h-5 text-emerald-500" />
              <h3 className="text-lg font-semibold text-white">
                Are your memories helping or hurting?
              </h3>
            </div>

            <div className="space-y-4 mb-4">
              <HealthRow icon={<XCircle className="w-4 h-4 text-red-400" />} label="Contradictions found" value={2} color="red" />
              <HealthRow icon={<Clock className="w-4 h-4 text-yellow-400" />} label="Stale memories" value={14} color="yellow" />
              <HealthRow icon={<AlertTriangle className="w-4 h-4 text-orange-400" />} label="Coverage gaps" value={3} color="orange" />
            </div>

            <div className="bg-zinc-950 rounded p-3 text-xs border-l-2 border-red-500">
              <span className="text-red-400 font-semibold">4 memories are actively causing hallucinations.</span>
              <span className="text-zinc-500 block mt-1">
                Memory #47, #112, #203, #89 — contradicted by newer data.
              </span>
            </div>
          </Card>

          {/* Card 3: Compliance */}
          <Card className={`p-6 transition-all duration-700 delay-300 ${inView ? 'animate-fade-in-up' : 'opacity-0'}`}>
            <div className="flex items-center gap-2 mb-4">
              <Shield className="w-5 h-5 text-emerald-500" />
              <h3 className="text-lg font-semibold text-white">
                Can you prove deletion to a regulator?
              </h3>
            </div>

            <ProvenanceMiniGraph />

            <div className="bg-zinc-950 rounded p-3 text-xs mt-4">
              <span className="text-zinc-400">
                <FileCheck className="w-3 h-3 inline mr-1 text-emerald-400" />
                Compliance certificate generated in <strong className="text-emerald-400">3 seconds</strong>.
                Cryptographic proof of cascading deletion across all derived data.
              </span>
            </div>
          </Card>
        </div>
      </div>
    </section>
  )
}

function HealthRow({ icon, label, value, color }: { icon: React.ReactNode; label: string; value: number; color: string }) {
  const bgColor = color === 'red' ? 'bg-red-400' : color === 'yellow' ? 'bg-yellow-400' : 'bg-orange-400'
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-zinc-300">
        {icon}
        {label}
      </div>
      <div className="flex items-center gap-2">
        <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div className={`h-full ${bgColor} rounded-full`} style={{ width: `${Math.min(value * 7, 100)}%` }} />
        </div>
        <span className="font-mono text-sm text-zinc-200 w-6 text-right">{value}</span>
      </div>
    </div>
  )
}

function ProvenanceMiniGraph() {
  const [deleted, setDeleted] = useState(false)

  useEffect(() => {
    const interval = setInterval(() => {
      setDeleted(true)
      setTimeout(() => setDeleted(false), 2500)
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="relative">
      <svg viewBox="0 0 280 120" className="w-full h-auto">
        {/* Edges */}
        <line x1="60" y1="60" x2="140" y2="30" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />
        <line x1="60" y1="60" x2="140" y2="60" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />
        <line x1="60" y1="60" x2="140" y2="90" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />
        <line x1="140" y1="30" x2="220" y2="45" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />
        <line x1="140" y1="60" x2="220" y2="45" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />
        <line x1="140" y1="90" x2="220" y2="80" stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" strokeDasharray={deleted ? '4 2' : 'none'} className="transition-all duration-500" />

        {/* User node */}
        <circle cx="60" cy="60" r="14" fill={deleted ? '#7f1d1d' : '#064e3b'} stroke={deleted ? '#ef4444' : '#10b981'} strokeWidth="2" className="transition-all duration-500" />
        <text x="60" y="64" textAnchor="middle" fill="white" fontSize="8" fontFamily="monospace">USER</text>

        {/* Memory nodes */}
        <circle cx="140" cy="30" r="10" fill={deleted ? '#450a0a' : '#18181b'} stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" className="transition-all duration-500" opacity={deleted ? 0.3 : 1} />
        <text x="140" y="33" textAnchor="middle" fill={deleted ? '#ef4444' : '#a1a1aa'} fontSize="6" fontFamily="monospace">MEM</text>

        <circle cx="140" cy="60" r="10" fill={deleted ? '#450a0a' : '#18181b'} stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" className="transition-all duration-500" opacity={deleted ? 0.3 : 1} />
        <text x="140" y="63" textAnchor="middle" fill={deleted ? '#ef4444' : '#a1a1aa'} fontSize="6" fontFamily="monospace">MEM</text>

        <circle cx="140" cy="90" r="10" fill={deleted ? '#450a0a' : '#18181b'} stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" className="transition-all duration-500" opacity={deleted ? 0.3 : 1} />
        <text x="140" y="93" textAnchor="middle" fill={deleted ? '#ef4444' : '#a1a1aa'} fontSize="6" fontFamily="monospace">EMB</text>

        {/* Response nodes */}
        <circle cx="220" cy="45" r="10" fill={deleted ? '#450a0a' : '#18181b'} stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" className="transition-all duration-500" opacity={deleted ? 0.3 : 1} />
        <text x="220" y="48" textAnchor="middle" fill={deleted ? '#ef4444' : '#a1a1aa'} fontSize="6" fontFamily="monospace">RSP</text>

        <circle cx="220" cy="80" r="10" fill={deleted ? '#450a0a' : '#18181b'} stroke={deleted ? '#ef4444' : '#3f3f46'} strokeWidth="1.5" className="transition-all duration-500" opacity={deleted ? 0.3 : 1} />
        <text x="220" y="83" textAnchor="middle" fill={deleted ? '#ef4444' : '#a1a1aa'} fontSize="6" fontFamily="monospace">RSP</text>

        {/* Deletion animation label */}
        {deleted && (
          <g>
            <rect x="70" y="100" width="140" height="18" rx="4" fill="#7f1d1d" />
            <text x="140" y="112" textAnchor="middle" fill="#ef4444" fontSize="8" fontFamily="monospace">
              GDPR CASCADE: DELETING...
            </text>
          </g>
        )}
      </svg>
      {!deleted && (
        <button
          onClick={() => setDeleted(true)}
          className="absolute bottom-0 right-0 flex items-center gap-1 text-xs text-zinc-500 hover:text-red-400 transition-colors font-mono"
        >
          <Trash2 className="w-3 h-3" />
          simulate deletion
        </button>
      )}
    </div>
  )
}

// ─── Section 4: Before/After ────────────────────────────────────────────────

function BeforeAfter() {
  const { ref, inView } = useInView(0.1)

  return (
    <section className="py-24 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <SectionLabel>The Difference</SectionLabel>
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-12">
          Before and after Cortexa
        </h2>

        <div className={`grid md:grid-cols-2 gap-6 transition-all duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          {/* Without */}
          <Card className="p-6 border-red-900/30 bg-red-950/5">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <h3 className="text-lg font-semibold text-red-400">Without Cortexa</h3>
            </div>

            <div className="space-y-5">
              <BeforeAfterRow
                icon={<XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />}
                title="Agent hallucinates"
                desc="You know something's wrong, but which memory? You check logs for 45 minutes, maybe you find it, maybe you don't."
              />
              <BeforeAfterRow
                icon={<Clock className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />}
                title="45 minutes to find root cause"
                desc="Manually diffing retrieved memories against outputs. Hope you guessed the right query to reproduce it."
              />
              <BeforeAfterRow
                icon={<DollarSign className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />}
                title="$38K/yr wasted on useless memories"
                desc="You're injecting memories into every prompt. Most contribute nothing. You have no way to know which ones."
              />
              <BeforeAfterRow
                icon={<Shield className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />}
                title='"We think we deleted everything?"'
                desc="GDPR request comes in. You delete the user row. But what about embeddings? Summaries? Cached responses?"
              />
            </div>
          </Card>

          {/* With */}
          <Card className="p-6 border-emerald-900/30 bg-emerald-950/5">
            <div className="flex items-center gap-2 mb-6">
              <div className="w-2 h-2 rounded-full bg-emerald-500" />
              <h3 className="text-lg font-semibold text-emerald-400">With Cortexa</h3>
            </div>

            <div className="space-y-5">
              <BeforeAfterRow
                icon={<CheckCircle className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />}
                title="Trace to root cause in 3 seconds"
                desc="Every response is attributed. Click the hallucination, see which memory caused it, see the fix."
              />
              <BeforeAfterRow
                icon={<Zap className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />}
                title="35% token reduction, saving $13K/yr"
                desc="Memory P&L shows exactly which memories earn their tokens and which are dead weight. Archive the losers."
              />
              <BeforeAfterRow
                icon={<TrendingUp className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />}
                title="Continuous memory health monitoring"
                desc="Contradictions, stale data, coverage gaps — surfaced automatically before they cause production issues."
              />
              <BeforeAfterRow
                icon={<FileCheck className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />}
                title="Cryptographic deletion certificate"
                desc="Provenance graph traces all derived data. One click cascades deletion. Certificate proves it to any regulator."
              />
            </div>
          </Card>
        </div>
      </div>
    </section>
  )
}

function BeforeAfterRow({ icon, title, desc }: { icon: React.ReactNode; title: string; desc: string }) {
  return (
    <div className="flex gap-3">
      {icon}
      <div>
        <p className="text-sm font-semibold text-zinc-200 mb-1">{title}</p>
        <p className="text-xs text-zinc-500 leading-relaxed">{desc}</p>
      </div>
    </div>
  )
}

// ─── Section 5: How It Works ────────────────────────────────────────────────

function HowItWorks() {
  const { ref, inView } = useInView(0.1)

  return (
    <section className="py-24 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <SectionLabel>Integration</SectionLabel>
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          Three steps. Ten minutes. No migration.
        </h2>
        <p className="text-zinc-400 mb-12 max-w-2xl">
          Cortexa wraps your existing memory system. No data migration, no vendor lock-in,
          no changes to your agent architecture.
        </p>

        <div className={`grid md:grid-cols-3 gap-8 mb-12 transition-all duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          <StepCard
            step={1}
            icon={<Layers className="w-6 h-6" />}
            title="Wrap your memory system"
            desc="One SDK call wraps Mem0, Zep, LangChain, or your custom memory layer. No migration, no data movement."
            code={`from cortexa import wrap\nmemory = wrap(your_memory)`}
          />
          <StepCard
            step={2}
            icon={<Zap className="w-6 h-6" />}
            title="Every query gets scored"
            desc="Fast attribution runs on 100% of queries in under 10ms. Deep causal analysis (Shapley values) runs on-demand for investigation."
            code={`# automatic — zero code\n# ~8ms p99 latency overhead`}
          />
          <StepCard
            step={3}
            icon={<Eye className="w-6 h-6" />}
            title="See what to fix"
            desc="Dashboard shows Memory P&L — what each memory costs vs. what it contributes. Health alerts fire before your users notice problems."
            code={`cortexa dashboard\n# → localhost:9400`}
          />
        </div>

        {/* Integration logos */}
        <div className="flex flex-wrap items-center justify-center gap-6 text-zinc-600 font-mono text-sm">
          <span className="text-zinc-500">Works with:</span>
          {['Mem0', 'Zep', 'LangChain', 'LlamaIndex', 'Custom Memory Systems'].map((name) => (
            <span key={name} className="px-3 py-1.5 rounded border border-zinc-800 bg-zinc-900/50 text-zinc-400 text-xs">
              {name}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

function StepCard({
  step,
  icon,
  title,
  desc,
  code,
}: {
  step: number
  icon: React.ReactNode
  title: string
  desc: string
  code: string
}) {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3 mb-4">
        <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-sm font-mono font-bold">
          {step}
        </div>
        <div className="text-emerald-500">{icon}</div>
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-zinc-400 mb-4 leading-relaxed">{desc}</p>
      <pre className="bg-zinc-950 rounded p-3 text-xs font-mono text-emerald-400/80 overflow-x-auto">
        {code}
      </pre>
    </Card>
  )
}

// ─── Section 6: Manifesto ───────────────────────────────────────────────────

function Manifesto() {
  const { ref, inView } = useInView(0.1)

  return (
    <section id="manifesto" className="py-24 px-6" ref={ref}>
      <div className={`max-w-3xl mx-auto transition-all duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
        <SectionLabel>Manifesto</SectionLabel>

        <div className="space-y-6 text-zinc-300 leading-relaxed">
          <h2 className="text-3xl sm:text-4xl font-bold text-white mb-8">
            Memory without observability is liability.
          </h2>

          <p>
            Every AI engineering team is building memory into their agents. Persistent context,
            user history, retrieved knowledge — it makes agents smarter, more personalized,
            more useful.
          </p>

          <p>
            But nobody is watching the memories.
          </p>

          <p className="text-zinc-200 font-medium">
            When your agent hallucinates, you can't tell which memory caused it.
            When your token bill spikes, you can't tell which memories are worth paying for.
            When a user requests deletion, you can't prove you got everything.
          </p>

          <p>
            Memory systems today are black boxes. Mem0, Zep, custom RAG stores — they all solve
            the same problem: <em>how to store and retrieve memories</em>. None of them solve
            the next problem: <em>how to know if those memories are helping or hurting</em>.
          </p>

          <p>
            This is the observability gap.
          </p>

          <p>
            Database engineers solved this decades ago. You wouldn't run Postgres without
            <code className="text-emerald-400 bg-emerald-950/30 px-1.5 py-0.5 rounded text-sm"> EXPLAIN ANALYZE</code>.
            You wouldn't deploy an API without distributed tracing. You wouldn't run a service
            without metrics and alerting.
          </p>

          <p>
            Yet every AI team is running memory systems blind. Injecting hundreds of memories
            into every prompt. Paying for tokens they don't need. Trusting data they haven't
            verified. Hoping nothing contradicts.
          </p>

          <p className="text-white font-medium text-lg">
            Cortexa is the observability layer for agent memory.
          </p>

          <p>
            For every response, we trace which memories influenced which claims. We score their
            contribution. We find the contradictions, the stale data, the coverage gaps. We show
            you which memories earn their tokens and which are dead weight.
          </p>

          <p>
            We don't replace your memory system. We make it accountable.
          </p>

          <div className="border-l-2 border-emerald-500 pl-4 py-2 my-8">
            <p className="text-emerald-400 font-mono text-sm">
              "If you can't measure it, you can't improve it. If you can't trace it, you can't
              trust it. If you can't prove deletion, you can't comply."
            </p>
          </div>

          <p className="text-zinc-500 text-sm">
            We're building for the teams running agents at scale — 10K queries/day, hundreds of
            memories per user, real compliance requirements. If that's you, we'd love to talk.
          </p>
        </div>
      </div>
    </section>
  )
}

// ─── Section 7: Cost of Silent Failures ─────────────────────────────────────

function CostOfFailures() {
  const { ref, inView } = useInView(0.1)

  return (
    <section className="py-24 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <SectionLabel>The Cost</SectionLabel>
        <h2 className="text-3xl sm:text-4xl font-bold text-white mb-4">
          The cost of silent failures
        </h2>
        <p className="text-zinc-400 mb-12 max-w-2xl">
          Memory problems don't crash your system. They quietly degrade trust,
          waste money, and create compliance risk. Here's what that looks like.
        </p>

        <div className={`grid md:grid-cols-2 gap-6 transition-all duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          <FailureCard
            variant="red"
            title="Hallucination from stale memory"
            metric="$14,000"
            metricLabel="avg. cost of a bad response to an enterprise customer"
            desc="A single stale memory makes your agent give wrong information. The customer escalates. Your team spends a day debugging. Trust takes months to rebuild."
            tag="Attribution Engine catches this"
          />
          <FailureCard
            variant="red"
            title="Token waste from dead memories"
            metric="$38,000"
            metricLabel="annual spend on memories with zero attribution"
            desc="You're injecting memories that contribute nothing to responses. They fill the context window, crowd out useful memories, and add latency. You'd never know without measurement."
            tag="Memory P&L reveals this"
          />
          <FailureCard
            variant="green"
            title="35% token reduction"
            metric="$13,300"
            metricLabel="annual savings from pruning zero-attribution memories"
            desc="Cortexa's Memory P&L identifies which memories earn their tokens. Archive the dead weight, boost the high-performers. Savings start on day one."
            tag="Lifecycle Engine optimizes this"
          />
          <FailureCard
            variant="green"
            title="GDPR compliance in seconds"
            metric="3s"
            metricLabel="time to generate a cryptographic deletion certificate"
            desc="Provenance graph traces every piece of derived data — embeddings, summaries, cached responses. One deletion cascade, one certificate. No more 'we think we got everything.'"
            tag="Compliance Engine handles this"
          />
        </div>
      </div>
    </section>
  )
}

function FailureCard({
  variant,
  title,
  metric,
  metricLabel,
  desc,
  tag,
}: {
  variant: 'red' | 'green'
  title: string
  metric: string
  metricLabel: string
  desc: string
  tag: string
}) {
  const isRed = variant === 'red'
  return (
    <Card className={`p-6 ${isRed ? 'border-red-900/30' : 'border-emerald-900/30'}`}>
      <div className="flex items-center gap-2 mb-3">
        {isRed ? (
          <AlertTriangle className="w-4 h-4 text-red-400" />
        ) : (
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        )}
        <h3 className="text-sm font-semibold text-zinc-200">{title}</h3>
      </div>
      <div className="mb-3">
        <span className={`text-3xl font-bold font-mono ${isRed ? 'text-red-400' : 'text-emerald-400'}`}>
          {metric}
        </span>
        <span className="text-xs text-zinc-500 block mt-1">{metricLabel}</span>
      </div>
      <p className="text-sm text-zinc-400 leading-relaxed mb-4">{desc}</p>
      <Badge variant={isRed ? 'yellow' : 'green'}>
        {isRed ? <Zap className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
        {tag}
      </Badge>
    </Card>
  )
}

// ─── Section 8: Footer with Waitlist ────────────────────────────────────────

const GOOGLE_SHEETS_URL =
  'https://script.google.com/macros/s/AKfycbzuIb5zHBtc-Y-Qs55ghMBPudpJivVrL7ihCfmbdK-LSE-swU48GGdquzijaKX12s7CVw/exec'

function WaitlistCTA() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault()
      if (!email.trim() || submitting) return

      setSubmitting(true)
      setError('')

      try {
        await fetch(GOOGLE_SHEETS_URL, {
          method: 'POST',
          mode: 'no-cors',
          headers: { 'Content-Type': 'text/plain' },
          body: JSON.stringify({ email: email.trim() }),
        })
        setSubmitted(true)
      } catch {
        setError('Something went wrong. Please try again.')
      } finally {
        setSubmitting(false)
      }
    },
    [email, submitting]
  )

  return (
    <section className="py-24 px-6 border-t border-zinc-800/50">
      <div className="max-w-2xl mx-auto text-center">
        <Brain className="w-10 h-10 text-emerald-500 mx-auto mb-6" />
        <h2 className="text-3xl font-bold text-white mb-4">
          Stop debugging blind.
        </h2>
        <p className="text-zinc-400 mb-8">
          Cortexa is in early access for teams running agents at scale.
          Join the waitlist — we'll reach out when your slot opens.
        </p>

        {submitted ? (
          <div className="flex items-center justify-center gap-2 text-emerald-400 font-mono">
            <CheckCircle className="w-5 h-5" />
            You're on the list. We'll be in touch.
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
            <input
              type="email"
              placeholder="you@company.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={submitting}
              className="flex-1 px-4 py-2.5 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-200 placeholder-zinc-600 text-sm font-mono focus:outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500/30 disabled:opacity-50"
            />
            <Button variant="primary" className={`whitespace-nowrap ${submitting ? 'opacity-70 pointer-events-none' : ''}`}>
              {submitting ? 'Sending...' : 'Join Waitlist'}
              <ArrowRight className="w-4 h-4" />
            </Button>
          </form>
        )}
        {error && (
          <p className="text-red-400 text-xs font-mono mt-3">{error}</p>
        )}
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className="py-8 px-6 border-t border-zinc-900">
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-zinc-600 text-sm">
          <Brain className="w-4 h-4" />
          <span className="font-mono">&copy; 2026 Cortexa</span>
        </div>
        <div className="flex items-center gap-6 text-xs text-zinc-600">
          <a href="#trace-demo" className="hover:text-zinc-400 transition-colors">How It Works</a>
          <a href="#manifesto" className="hover:text-zinc-400 transition-colors">Manifesto</a>
          <a
            href="https://github.com/cortexa"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-zinc-400 transition-colors flex items-center gap-1"
          >
            GitHub
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>
    </footer>
  )
}

// ─── Nav ────────────────────────────────────────────────────────────────────

function Nav() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50)
    window.addEventListener('scroll', onScroll)
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled
          ? 'bg-zinc-950/90 backdrop-blur-md border-b border-zinc-800/50'
          : 'bg-transparent'
      }`}
    >
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-emerald-500" />
          <span className="font-mono font-bold text-white text-sm tracking-tight">CORTEXA</span>
        </div>
        <div className="hidden sm:flex items-center gap-6 text-xs text-zinc-500">
          <a href="#trace-demo" className="hover:text-zinc-300 transition-colors">Demo</a>
          <a href="#manifesto" className="hover:text-zinc-300 transition-colors">Manifesto</a>
          <Button
            variant="primary"
            className="text-xs px-3 py-1.5"
            onClick={() =>
              document.querySelector('input[type="email"]')?.scrollIntoView({ behavior: 'smooth' })
            }
          >
            <Terminal className="w-3 h-3" />
            Get Early Access
          </Button>
        </div>
      </div>
    </nav>
  )
}

// ─── App ────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <div className="min-h-screen bg-[#0a0a0a] text-zinc-200 selection:bg-emerald-500/20">
      <Nav />
      <Hero />
      <TraceDemo />
      <ThreeQuestions />
      <BeforeAfter />
      <HowItWorks />
      <Manifesto />
      <CostOfFailures />
      <WaitlistCTA />
      <Footer />
    </div>
  )
}
