import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Search, Shield, Zap, ArrowRight, AlertTriangle,
  CheckCircle, XCircle, Clock, DollarSign, TrendingUp,
  Eye, FileCheck, ChevronDown, Terminal, Activity,
  Trash2, ExternalLink, Layers, Github,
} from 'lucide-react'

// ─── Hooks ───────────────────────────────────────────────────────────────────

function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [inView, setInView] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setInView(true); obs.unobserve(el) }
    }, { threshold })
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, inView }
}

function useStagger(inView: boolean, steps: number, ms = 420) {
  const [step, setStep] = useState(0)
  useEffect(() => {
    if (!inView || step >= steps) return
    const t = setTimeout(() => setStep(s => s + 1), ms)
    return () => clearTimeout(t)
  }, [inView, step, steps, ms])
  return step
}

// ─── Logo ─────────────────────────────────────────────────────────────────────

function Logo({ className = 'logo-img-nav' }: { className?: string }) {
  return (
    <img
      src="/cortexalogo.jpeg"
      alt="Cortexa"
      className={`${className} rounded-lg anim-logo`}
    />
  )
}

// ─── Aurora background ────────────────────────────────────────────────────────

function Aurora() {
  return (
    <div className="aurora" aria-hidden>
      <div className="aurora-blob" />
      <div className="aurora-blob" />
      <div className="aurora-blob" />
    </div>
  )
}

// ─── Section label ────────────────────────────────────────────────────────────

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

// ─── Nav ──────────────────────────────────────────────────────────────────────

function Nav() {
  const [scrolled, setScrolled] = useState(false)
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 40)
    window.addEventListener('scroll', fn, { passive: true })
    return () => window.removeEventListener('scroll', fn)
  }, [])

  const navLink = { color: 'var(--text)' } as const

  return (
    <nav className={`nav-base ${scrolled ? 'nav-scrolled' : ''}`}>
      {/* Left: logo + section links */}
      <div className="flex items-center gap-6">
        <Logo className="logo-img-nav" />
        <div className="hidden sm:flex items-center gap-5">
          {[
            { href: '#demo',         label: 'Demo' },
            { href: '#how-it-works', label: 'How It Works' },
            { href: '#manifesto',    label: 'Manifesto' },
            { href: '#faq',          label: 'FAQ' },
          ].map(({ href, label }) => (
            <a key={href} href={href} className="text-sm font-medium transition-colors" style={navLink}>
              {label}
            </a>
          ))}
        </div>
      </div>

      {/* Right: GitHub + CTA */}
      <div className="hidden sm:flex items-center gap-4">
        <a
          href="https://github.com/Arunjay4213/Cortexa"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center transition-colors"
          style={navLink}
        >
          <Github size={16} />
        </a>
        <button
          className="btn-primary text-xs px-4 py-2"
          onClick={() => document.querySelector<HTMLInputElement>('input[type="email"]')
            ?.scrollIntoView({ behavior: 'smooth' })}
        >
          <Terminal size={13} />
          Early Access
        </button>
      </div>
    </nav>
  )
}

// ─── Hero ─────────────────────────────────────────────────────────────────────

function Hero() {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-24 pb-16 text-center overflow-hidden">
      <Aurora />

      {/* Radial vignette — darkens edges, focuses on center */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 80% 70% at 50% 40%, transparent 40%, rgba(28,28,30,0.04) 100%)' }} />

      <div className="relative z-10 max-w-5xl mx-auto">

        {/* Logo — large, solo, let it speak */}
        <div className="flex justify-center mb-10 anim-fade-up hidden-init d-1">
          <Logo className="logo-img" />
        </div>

        {/* Pill badge */}
        <div className="flex justify-center mb-8 anim-fade-up hidden-init d-2">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-mono border"
            style={{ background: 'rgba(122,140,0,0.10)', borderColor: 'rgba(122,140,0,0.22)', color: 'var(--lime)' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-lime-500 animate-pulse" />
            Early Access — Now Open
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-bold leading-[1.08] tracking-tight mb-7 anim-fade-up hidden-init d-3"
          style={{ fontSize: 'clamp(2.8rem, 5vw + 1rem, 5.5rem)', color: 'var(--text)' }}>
          Your agent hallucinated.
          <br />
          <span style={{ color: 'var(--lime)' }}>Which memory caused it?</span>
        </h1>

        {/* Subhead */}
        <p className="max-w-2xl mx-auto mb-12 font-light anim-fade-up hidden-init d-4"
          style={{ fontSize: 'clamp(1.05rem, 0.5vw + 0.9rem, 1.25rem)', color: 'var(--muted)', lineHeight: 1.7 }}>
          Cortexa traces every LLM response back to the memories that shaped it.
          Find the root cause in seconds. Fix it before your users notice.
        </p>

        {/* CTA row */}
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4 anim-fade-up hidden-init d-5">
          <button className="btn-primary"
            onClick={() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })}>
            See How It Works
            <ArrowRight size={16} />
          </button>
          <button className="btn-secondary"
            onClick={() => document.getElementById('manifesto')?.scrollIntoView({ behavior: 'smooth' })}>
            Read the Manifesto
          </button>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-6 max-w-xl mx-auto mt-20 anim-fade-up hidden-init"
          style={{ animationDelay: '0.85s' }}>
          {[
            { n: '3s', label: 'root cause trace' },
            { n: '35%', label: 'context noise reduction' },
            { n: '42%', label: 'Ghost Token recovery' },
          ].map(({ n, label }) => (
            <div key={label} className="text-center">
              <div className="stat-number" style={{ color: 'var(--lime)' }}>{n}</div>
              <div className="text-xs mt-1.5 font-mono" style={{ color: 'var(--muted)' }}>{label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Scroll cue */}
      <div className="absolute bottom-10 left-1/2 -translate-x-1/2 anim-bounce" style={{ color: 'var(--muted)', opacity: 0.4 }}>
        <ChevronDown size={20} />
      </div>
    </section>
  )
}

// ─── Trace Demo ───────────────────────────────────────────────────────────────

function TraceDemo() {
  const { ref, inView } = useInView(0.1)
  const step = useStagger(inView, 5, 550)

  return (
    <section id="demo" className="py-28 px-6" ref={ref}>
      <div className="max-w-4xl mx-auto">
        <Label>Live Trace</Label>
        <h2 className="font-bold mb-4 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Wrong answer. Root cause in 2 seconds.
        </h2>
        <p className="mb-12 max-w-xl" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
          An AI agent gives a customer the wrong shipping date. Cortexa finds exactly
          which memory caused it — and fixes it before anyone else is affected.
        </p>

        <div className="terminal-win">
          <div className="terminal-titlebar">
            <div className="dot dot-r" />
            <div className="dot dot-y" />
            <div className="dot dot-g" />
            <span className="text-xs font-mono ml-3" style={{ color: 'var(--muted)' }}>
              cortexa monitor --agent support-bot
            </span>
          </div>

          <div className="p-7 sm:p-10 font-mono text-sm space-y-5">

            {/* Step 1 — wrong answer */}
            {step >= 1 && (
              <div className="anim-fade-up hidden-init">
                <div className="flex items-center gap-2 text-xs mb-2" style={{ color: '#B91C1C' }}>
                  <XCircle size={13} /> HALLUCINATION DETECTED
                </div>
                <div className="rounded-xl p-4" style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.22)' }}>
                  <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>Agent told the customer:</p>
                  <p style={{ color: '#B91C1C' }}>"Your order will arrive in <strong>2 business days</strong>. Standard shipping is free!"</p>
                  <p className="text-xs mt-2" style={{ color: '#9F1239' }}>
                    <AlertTriangle size={10} className="inline mr-1" />
                    Conflicts with current policy — shipping is now 5–7 days
                  </p>
                </div>
              </div>
            )}

            {/* Step 2 — attribution trace */}
            {step >= 2 && (
              <div className="anim-fade-up hidden-init">
                <div className="flex items-center gap-2 text-xs mb-3" style={{ color: 'var(--muted)', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                  <Search size={12} /> ATTRIBUTION TRACE — culprit found
                </div>
                <div className="rounded-xl p-4 anim-pulse-red" style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.22)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span style={{ color: 'var(--text)' }}>Memory #47</span>
                      <span className="px-2 py-0.5 rounded text-xs" style={{ background: 'rgba(239,68,68,0.15)', color: '#B91C1C', border: '1px solid rgba(239,68,68,0.3)' }}>
                        attribution: 0.86
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-xs flex items-center gap-1" style={{ background: 'rgba(239,68,68,0.15)', color: '#B91C1C', border: '1px solid rgba(239,68,68,0.3)' }}>
                      <AlertTriangle size={10} /> STALE
                    </span>
                  </div>
                  <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>"Standard shipping: 2 business days, free over $35"</p>
                  <p className="text-xs" style={{ color: '#9F1239' }}>
                    <Clock size={10} className="inline mr-1" />
                    Last updated 9 months ago — predates Jan 15 policy change
                  </p>
                </div>
              </div>
            )}

            {/* Step 3 — correct memory was there, just buried */}
            {step >= 3 && (
              <div className="anim-slide-left hidden-init">
                <div className="rounded-xl p-4" style={{ background: 'var(--lime-dim)', border: '1px solid rgba(122,140,0,0.20)' }}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span style={{ color: 'var(--text)' }}>Memory #203</span>
                      <span className="px-2 py-0.5 rounded text-xs" style={{ background: 'rgba(122,140,0,0.14)', color: 'var(--lime)', border: '1px solid rgba(122,140,0,0.25)' }}>
                        attribution: 0.07
                      </span>
                    </div>
                    <span className="px-2 py-0.5 rounded text-xs flex items-center gap-1" style={{ background: 'rgba(122,140,0,0.14)', color: 'var(--lime)', border: '1px solid rgba(122,140,0,0.25)' }}>
                      <CheckCircle size={10} /> CURRENT
                    </span>
                  </div>
                  <p className="text-xs mb-1" style={{ color: 'var(--muted)' }}>"Shipping policy updated Jan 15: standard delivery now 5–7 days"</p>
                  <p className="text-xs" style={{ color: '#78350F' }}>
                    <AlertTriangle size={10} className="inline mr-1" />
                    Retrieved but ranked 4th — correct memory was buried
                  </p>
                </div>
              </div>
            )}

            {/* Step 4 — fix */}
            {step >= 4 && (
              <div className="anim-fade-up hidden-init">
                <div className="rounded-xl p-4" style={{ background: 'rgba(28,28,30,0.04)', border: '1px solid var(--border)' }}>
                  <div className="flex items-center gap-2 text-xs mb-2" style={{ color: 'var(--lime)' }}>
                    <Zap size={13} /> CORTEXA FIX
                  </div>
                  <ul className="text-xs space-y-1" style={{ color: 'var(--muted)' }}>
                    <li>→ Memory #47 invalidated (contradicted by Jan 15 update)</li>
                    <li>→ Memory #203 promoted to rank 1</li>
                    <li>→ 6 similar outdated shipping memories flagged for review</li>
                  </ul>
                </div>
              </div>
            )}

            {/* Step 5 — corrected + time */}
            {step >= 5 && (
              <div className="anim-fade-up hidden-init">
                <div className="flex items-center gap-2 text-xs mb-2" style={{ color: 'var(--lime)' }}>
                  <CheckCircle size={13} /> CORRECTED RESPONSE
                </div>
                <div className="rounded-xl p-4 anim-pulse-lime" style={{ background: 'var(--lime-dim)', border: '1px solid rgba(122,140,0,0.22)' }}>
                  <p style={{ color: 'var(--text)' }}>"Your order will arrive in <strong>5–7 business days</strong>. Standard shipping is free over $35!"</p>
                </div>
                <div className="flex items-center justify-between mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
                  <div className="flex items-center gap-2">
                    <Activity size={14} style={{ color: 'var(--lime)' }} />
                    <span className="text-xs" style={{ color: 'var(--lime)' }}>Root cause found in <strong>2.3 seconds</strong></span>
                  </div>
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>previously: 45 min of log archaeology</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── Three Questions ──────────────────────────────────────────────────────────

function ThreeQuestions() {
  const { ref, inView } = useInView(0.08)

  return (
    <section className="py-28 px-6" ref={ref}>
      <div className="max-w-6xl mx-auto">
        <Label>The Blind Spots</Label>
        <h2 className="font-bold mb-4 tracking-tight max-w-xl"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Three questions you can't answer today
        </h2>
        <p className="mb-14 max-w-xl" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
          You're running thousands of queries through memories every day.
          But can you answer these?
        </p>

        <div className="grid md:grid-cols-3 gap-5">

          {/* Card 1: Attribution Density — previously Memory P&L */}
          <div className={`card p-7 transition-all duration-700 ${inView ? 'anim-fade-up' : 'hidden-init'}`}>
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(122,140,0,0.12)' }}>
                <TrendingUp size={17} style={{ color: 'var(--lime)' }} />
              </div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text)' }}>
                What's your Memory Attribution Score?
              </h3>
            </div>
            <div className="font-mono text-xs mb-5">
              <div className="grid grid-cols-4 gap-2 pb-2 mb-2 border-b" style={{ borderColor: 'var(--border)', color: 'var(--muted)' }}>
                <span>MEM</span><span className="text-right">LATENCY</span>
                <span className="text-right">ATTR</span><span className="text-right">ROI</span>
              </div>
              {[
                { name: 'user_prefs', latency: 'Low',  attr: '0.89', roi: 'High',     status: 'good' },
                { name: 'rag_docs',   latency: 'Med',  attr: '0.47', roi: 'Variable', status: 'neutral' },
                { name: 'old_convos', latency: 'High', attr: '0.03', roi: 'Ghost',    status: 'bad' },
                { name: 'raw_logs',   latency: 'High', attr: '0.01', roi: 'Ghost',    status: 'bad' },
              ].map(r => (
                <div key={r.name} className={`grid grid-cols-4 gap-2 py-1.5 rounded ${r.status === 'bad' ? '-mx-1 px-1' : ''}`}
                  style={{ background: r.status === 'bad' ? 'rgba(239,68,68,0.07)' : 'transparent' }}>
                  <span className="truncate" style={{ color: r.status === 'bad' ? '#B91C1C' : 'var(--text)' }}>{r.name}</span>
                  <span className="text-right" style={{ color: 'var(--muted)' }}>{r.latency}</span>
                  <span className="text-right" style={{ color: r.status === 'good' ? 'var(--lime)' : r.status === 'neutral' ? '#B45309' : '#B91C1C' }}>{r.attr}</span>
                  <span className="text-right" style={{ color: r.status === 'good' ? 'var(--lime)' : r.status === 'neutral' ? '#B45309' : '#B91C1C' }}>{r.roi}</span>
                </div>
              ))}
            </div>
            <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(28,28,30,0.04)', border: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--muted)' }}>
                <strong style={{ color: '#B91C1C' }}>2 Ghost Token sources</strong> detected.
                Recovering <strong style={{ color: 'var(--lime)' }}>14% of context window</strong>.
              </span>
            </div>
          </div>

          {/* Card 2: Health */}
          <div className={`card p-7 transition-all duration-700 delay-150 ${inView ? 'anim-fade-up' : 'hidden-init'}`}>
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(122,140,0,0.12)' }}>
                <Activity size={17} style={{ color: 'var(--lime)' }} />
              </div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text)' }}>
                Are your memories helping or hurting?
              </h3>
            </div>
            <div className="space-y-4 mb-5">
              {[
                { icon: <XCircle size={14} style={{ color: '#B91C1C' }} />, label: 'Contradictions', val: 2, pct: 14, color: '#B91C1C' },
                { icon: <Clock size={14} style={{ color: '#B45309' }} />, label: 'Stale memories', val: 14, pct: 98, color: '#B45309' },
                { icon: <AlertTriangle size={14} style={{ color: '#C2410C' }} />, label: 'Coverage gaps', val: 3, pct: 21, color: '#C2410C' },
              ].map(r => (
                <div key={r.label} className="flex items-center justify-between">
                  <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--text)' }}>
                    {r.icon} {r.label}
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-20 h-1 rounded-full" style={{ background: 'rgba(28,28,30,0.09)' }}>
                      <div className="h-full rounded-full" style={{ width: `${r.pct}%`, background: r.color }} />
                    </div>
                    <span className="font-mono text-sm w-5 text-right" style={{ color: 'var(--text)' }}>{r.val}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="rounded-lg p-3 text-xs border-l-2" style={{ background: 'rgba(239,68,68,0.07)', borderLeftColor: '#ef4444' }}>
              <span className="font-semibold" style={{ color: '#B91C1C' }}>4 memories are actively causing wrong answers.</span>
              <span className="block mt-1" style={{ color: 'var(--muted)' }}>Memory #47, #112, #203, #89 — contradicted by newer data.</span>
            </div>
          </div>

          {/* Card 3: Compliance */}
          <div className={`card p-7 transition-all duration-700 delay-300 ${inView ? 'anim-fade-up' : 'hidden-init'}`}>
            <div className="flex items-center gap-2.5 mb-5">
              <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'rgba(122,140,0,0.12)' }}>
                <Shield size={17} style={{ color: 'var(--lime)' }} />
              </div>
              <h3 className="text-base font-semibold" style={{ color: 'var(--text)' }}>
                Can you prove deletion to a regulator?
              </h3>
            </div>
            <ProvenanceGraph />
            <div className="rounded-lg p-3 text-xs mt-4" style={{ background: 'rgba(28,28,30,0.04)', border: '1px solid var(--border)' }}>
              <span style={{ color: 'var(--muted)' }}>
                <FileCheck size={11} className="inline mr-1" style={{ color: 'var(--lime)' }} />
                Compliance certificate generated in{' '}
                <strong style={{ color: 'var(--lime)' }}>3 seconds</strong>.
                Cryptographic proof of cascading deletion.
              </span>
            </div>
          </div>
        </div>

        {/* MAS Benchmark callout */}
        <div className={`mt-10 rounded-2xl p-7 transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}
          style={{ background: 'rgba(122,140,0,0.06)', border: '1px solid rgba(122,140,0,0.2)' }}>
          <div className="flex items-center gap-2 mb-5">
            <Activity size={13} style={{ color: 'var(--lime)' }} />
            <span className="text-xs font-mono font-semibold tracking-widest" style={{ color: 'var(--lime)' }}>CORTEXA BENCHMARKS</span>
          </div>
          <div className="grid md:grid-cols-3 gap-8">
            <div>
              <p className="text-xs font-mono mb-1" style={{ color: 'var(--muted)' }}>MAS — Memory Attribution Score</p>
              <p className="text-sm leading-relaxed" style={{ color: 'var(--text)' }}>
                The percentage of retrieved context that actually influences the final logit.
                Low MAS = context noise. High MAS = efficient inference.
              </p>
            </div>
            <div>
              <p className="text-xs font-mono mb-2" style={{ color: 'var(--muted)' }}>PRODUCTION TARGET</p>
              <div className="font-bold" style={{ fontSize: '2rem', color: 'var(--lime)', lineHeight: 1 }}>MAS &gt; 75%</div>
              <p className="text-xs mt-2" style={{ color: 'var(--muted)' }}>Below this threshold, embedding drift and retrieval rank bias introduce measurable response degradation.</p>
            </div>
            <div className="space-y-3">
              {[
                { range: 'MAS &gt; 75%', label: 'Production ready',     color: 'var(--lime)' },
                { range: 'MAS 25–75%', label: 'Optimization needed',   color: '#B45309' },
                { range: 'MAS &lt; 25%', label: 'Critical context noise', color: '#B91C1C' },
              ].map(b => (
                <div key={b.label} className="flex items-center justify-between">
                  <span className="text-xs font-mono" style={{ color: b.color }} dangerouslySetInnerHTML={{ __html: b.range }} />
                  <span className="text-xs" style={{ color: 'var(--muted)' }}>{b.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

function ProvenanceGraph() {
  const [deleted, setDeleted] = useState(false)
  useEffect(() => {
    const iv = setInterval(() => {
      setDeleted(true)
      setTimeout(() => setDeleted(false), 2600)
    }, 5200)
    return () => clearInterval(iv)
  }, [])

  const lineColor = deleted ? '#ef4444' : 'rgba(28,28,30,0.18)'
  const dash = deleted ? '4 3' : 'none'

  return (
    <div className="relative">
      <svg viewBox="0 0 280 120" className="w-full">
        {[[60,60,140,30],[60,60,140,60],[60,60,140,90],
          [140,30,220,45],[140,60,220,45],[140,90,220,80]].map(([x1,y1,x2,y2], i) => (
          <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
            stroke={lineColor} strokeWidth="1.5" strokeDasharray={dash}
            className="transition-all duration-500" />
        ))}
        <circle cx="60" cy="60" r="14"
          fill={deleted ? '#7f1d1d' : 'rgba(122,140,0,0.12)'}
          stroke={deleted ? '#ef4444' : 'var(--lime)'}
          strokeWidth="1.5" className="transition-all duration-500" />
        <text x="60" y="64" textAnchor="middle" fill="white" fontSize="7" fontFamily="monospace">USER</text>
        {[[140,30],[140,60],[140,90],[220,45],[220,80]].map(([cx,cy], i) => (
          <g key={i}>
            <circle cx={cx} cy={cy} r="10"
              fill={deleted ? '#450a0a' : 'rgba(28,28,30,0.05)'}
              stroke={deleted ? '#ef4444' : 'rgba(28,28,30,0.15)'}
              strokeWidth="1.5"
              opacity={deleted ? 0.35 : 1}
              className="transition-all duration-500" />
            <text x={cx} y={cy+3} textAnchor="middle"
              fill={deleted ? '#ef4444' : 'rgba(28,28,30,0.55)'}
              fontSize="6" fontFamily="monospace">
              {i < 3 ? 'MEM' : 'RSP'}
            </text>
          </g>
        ))}
        {deleted && (
          <g>
            <rect x="65" y="100" width="150" height="16" rx="4" fill="rgba(127,29,29,0.8)" />
            <text x="140" y="111" textAnchor="middle" fill="#ef4444" fontSize="7" fontFamily="monospace">
              GDPR CASCADE: DELETING...
            </text>
          </g>
        )}
      </svg>
      {!deleted && (
        <button onClick={() => setDeleted(true)}
          className="absolute bottom-0 right-0 flex items-center gap-1 text-xs font-mono transition-colors"
          style={{ color: 'var(--muted)' }}
          onMouseEnter={e => (e.currentTarget.style.color = '#B91C1C')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}>
          <Trash2 size={11} /> simulate deletion
        </button>
      )}
    </div>
  )
}

// ─── Before / After ───────────────────────────────────────────────────────────

function BeforeAfter() {
  const { ref, inView } = useInView(0.08)

  return (
    <section className="py-28 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <Label>The Difference</Label>
        <h2 className="font-bold mb-14 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Before and after Cortexa
        </h2>

        <div className={`grid md:grid-cols-2 gap-6 transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          <div className="card p-7" style={{ borderColor: 'rgba(239,68,68,0.15)', background: 'rgba(239,68,68,0.03)' }}>
            <div className="flex items-center gap-2 mb-7">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <h3 className="text-base font-semibold" style={{ color: '#B91C1C' }}>Without Cortexa</h3>
            </div>
            <div className="space-y-6">
              {[
                { icon: <XCircle size={15} style={{ color: '#B91C1C' }} />, t: 'Agent gives wrong answer', d: "You know something's wrong. Which memory? You dig through logs for 45 minutes. Maybe you find it." },
                { icon: <Clock size={15} style={{ color: '#B91C1C' }} />, t: '45 minutes to root cause', d: "Manually diffing retrieved memories against outputs. Hoping you can reproduce the query." },
                { icon: <DollarSign size={15} style={{ color: '#B91C1C' }} />, t: '$38K/yr on dead memories', d: "Injecting memories that contribute nothing. They crowd context, add latency. No way to know which." },
                { icon: <Shield size={15} style={{ color: '#B91C1C' }} />, t: '"We think we deleted everything"', d: "GDPR request arrives. You delete the row. But the embeddings? Summaries? Cached responses?" },
              ].map(r => (
                <div key={r.t} className="flex gap-3">
                  <div className="mt-0.5 flex-shrink-0">{r.icon}</div>
                  <div>
                    <p className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>{r.t}</p>
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>{r.d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card p-7" style={{ borderColor: 'rgba(122,140,0,0.15)', background: 'rgba(122,140,0,0.02)' }}>
            <div className="flex items-center gap-2 mb-7">
              <div className="w-2 h-2 rounded-full" style={{ background: 'var(--lime)' }} />
              <h3 className="text-base font-semibold" style={{ color: 'var(--lime)' }}>With Cortexa</h3>
            </div>
            <div className="space-y-6">
              {[
                { icon: <CheckCircle size={15} style={{ color: 'var(--lime)' }} />, t: 'Trace to root cause in 3 seconds', d: "Every response is attributed. Run cx.trace(), see which memory caused it, see the exact fix." },
                { icon: <Zap size={15} style={{ color: 'var(--lime)' }} />, t: '35% token reduction, saving $13K/yr', d: "Memory P&L shows what earns its tokens and what's dead weight. Archive the losers." },
                { icon: <TrendingUp size={15} style={{ color: 'var(--lime)' }} />, t: 'Continuous memory health monitoring', d: "Contradictions, stale data, duplicates — surfaced before they hit production." },
                { icon: <FileCheck size={15} style={{ color: 'var(--lime)' }} />, t: 'Cryptographic deletion certificate', d: "Provenance graph traces all derived data. One cascade. One certificate. Regulators satisfied." },
              ].map(r => (
                <div key={r.t} className="flex gap-3">
                  <div className="mt-0.5 flex-shrink-0">{r.icon}</div>
                  <div>
                    <p className="text-sm font-semibold mb-1" style={{ color: 'var(--text)' }}>{r.t}</p>
                    <p className="text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>{r.d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

// ─── How It Works ─────────────────────────────────────────────────────────────

function HowItWorks() {
  const { ref, inView } = useInView(0.08)

  const steps = [
    {
      n: 1, icon: <Layers size={20} />,
      title: 'Install the SDK',
      desc: 'One pip install. Wraps Mem0, SuperMemory, or your custom memory layer. No data migration, no architecture changes.',
      code: `pip install cortexos\n\nfrom cortexos import Cortex\ncx = Cortex(api_key="cx-...")`,
    },
    {
      n: 2, icon: <Zap size={20} />,
      title: 'Gate every memory write',
      desc: 'cx.gate() verifies grounding before anything gets stored. Wrong memories are blocked at the source, not debugged after the fact.',
      code: `result = cx.gate(\n  memory="user prefers express",\n  sources=[context_docs]\n)\nif result.grounded:\n  store(memory)`,
    },
    {
      n: 3, icon: <Eye size={20} />,
      title: 'Trace bad answers instantly',
      desc: 'When an agent goes wrong, cx.trace() finds the culprit memory in seconds. No log archaeology. No guessing.',
      code: `trace = cx.trace(\n  "wrong answer text"\n)\nprint(trace.matches[0].memory)\n# → the memory that caused it`,
    },
  ]

  return (
    <section id="how-it-works" className="py-28 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <Label>Integration</Label>
        <h2 className="font-bold mb-4 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Three steps. Ten minutes. No migration.
        </h2>
        <p className="mb-14 max-w-xl" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
          Cortexa sits in front of your existing memory system — no data movement,
          no vendor lock-in, no changes to your agent.
        </p>

        <div className={`grid md:grid-cols-3 gap-5 mb-14 transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          {steps.map(s => (
            <div key={s.n} className="card p-7">
              <div className="flex items-center gap-3 mb-5">
                <div className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-mono font-bold"
                  style={{ background: 'rgba(122,140,0,0.12)', border: '1px solid rgba(122,140,0,0.25)', color: 'var(--lime)' }}>
                  {s.n}
                </div>
                <div style={{ color: 'var(--lime)' }}>{s.icon}</div>
              </div>
              <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text)' }}>{s.title}</h3>
              <p className="text-sm mb-5 leading-relaxed" style={{ color: 'var(--muted)' }}>{s.desc}</p>
              <pre className="rounded-xl p-4 text-xs font-mono overflow-x-auto"
                style={{ background: 'rgba(28,28,30,0.06)', color: '#1C1C1E', border: '1px solid rgba(28,28,30,0.14)' }}>
                {s.code}
              </pre>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>Works with:</span>
          {['Mem0', 'SuperMemory', 'LangChain', 'LlamaIndex', 'Custom Memory'].map(n => (
            <span key={n} className="px-3 py-1.5 rounded-lg text-xs font-mono"
              style={{ background: 'rgba(28,28,30,0.05)', border: '1px solid var(--border)', color: 'rgba(28,28,30,0.50)' }}>
              {n}
            </span>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Manifesto ────────────────────────────────────────────────────────────────

function Manifesto() {
  const { ref, inView } = useInView(0.08)

  return (
    <section id="manifesto" className="py-28 px-6" ref={ref}>
      <div className={`max-w-3xl mx-auto transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
        <Label>Manifesto</Label>

        <h2 className="font-bold mb-12 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Memory without observability is liability.
        </h2>

        <div className="space-y-6 text-base leading-[1.75]" style={{ color: 'rgba(28,28,30,0.70)' }}>
          <p>
            Every AI engineering team is building memory into their agents. Persistent context,
            user history, retrieved knowledge — it makes agents smarter, more personalized, more useful.
          </p>
          <p>But nobody is watching the memories.</p>
          <p style={{ color: 'var(--text)', fontWeight: 500 }}>
            When your agent gives a wrong answer, you can't tell which memory caused it.
            When your token bill spikes, you can't tell which memories are worth paying for.
            When a user requests deletion, you can't prove you got everything.
          </p>
          <p>
            Memory systems today are black boxes. Mem0, Zep, custom RAG stores — they all solve
            the same problem: <em>how to store and retrieve memories</em>. None of them solve
            the next one: <em>how to know if those memories are helping or hurting</em>.
          </p>
          <p>This is the observability gap.</p>
          <p>
            Database engineers solved this decades ago. You wouldn't run Postgres without
            <code className="px-1.5 py-0.5 rounded text-sm mx-1 font-mono"
              style={{ background: 'rgba(122,140,0,0.12)', color: 'var(--lime)' }}>
              EXPLAIN ANALYZE
            </code>.
            You wouldn't ship an API without distributed tracing. You wouldn't run a service
            without metrics and alerting.
          </p>
          <p>
            Yet every AI team is running memory systems blind. Injecting hundreds of memories
            into every prompt. Paying for tokens they don't need. Trusting data they haven't
            verified. Hoping nothing contradicts.
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Cortexa is the observability layer for agent memory.
          </p>
          <p>
            For every response, we trace which memories influenced which claims. We score their
            contribution. We find contradictions, stale data, and coverage gaps. We show you
            which memories earn their tokens and which are dead weight.
          </p>
          <p>We don't replace your memory system. We make it accountable.</p>

          <blockquote className="my-10 pl-5 py-1 border-l-2" style={{ borderColor: 'var(--lime)' }}>
            <p className="font-mono text-sm" style={{ color: 'var(--lime)' }}>
              "If you can't measure it, you can't improve it. If you can't trace it, you can't
              trust it. If you can't prove deletion, you can't comply."
            </p>
          </blockquote>

          <p className="text-sm" style={{ color: 'rgba(28,28,30,0.35)' }}>
            We're building for teams running agents at scale — 10K queries/day, hundreds of
            memories per user, real compliance requirements. If that's you, we'd love to talk.
          </p>
        </div>
      </div>
    </section>
  )
}

// ─── Cost Cards ───────────────────────────────────────────────────────────────

function CostSection() {
  const { ref, inView } = useInView(0.08)

  const cards = [
    { bad: true,  metric: '47 min', sub: 'avg time-to-root-cause without attribution tracing',
      title: 'High-latency debugging & eroded trust',
      desc: 'A stale memory causes a wrong answer. Without attribution tracing, engineers manually diff retrieved memories against outputs — 45+ minutes of log archaeology per incident. Every unresolved hallucination widens the embedding drift.',
      tag: 'Attribution Engine catches this' },
    { bad: true,  metric: '~42%', sub: 'of retrieved context are Ghost Tokens — influencing nothing',
      title: 'Blind Token Inflation',
      desc: 'Ghost Tokens are memories retrieved but never used by the LLM. They inflate context size, increase inference latency, and crowd out high-attribution memories — all without contributing to the final logit.',
      tag: 'Memory P&L reveals this' },
    { bad: false, metric: '+14%', sub: 'context window recovered via attribution pruning',
      title: 'Context Window Optimization',
      desc: 'Attribution density scoring identifies Ghost Tokens automatically. Pruning them recovers context headroom for high-MAS memories, reduces latency, and lowers context noise — measurable on day one.',
      tag: 'Lifecycle Engine optimizes this' },
    { bad: false, metric: '3s', sub: 'to generate a cryptographic deletion certificate',
      title: 'GDPR compliance in seconds',
      desc: 'Provenance graph traces all derived data — embeddings, summaries, cached responses. One cascade deletion. One certificate. No guesswork about what downstream data still carries the original signal.',
      tag: 'Compliance Engine handles this' },
  ]

  return (
    <section className="py-28 px-6" ref={ref}>
      <div className="max-w-5xl mx-auto">
        <Label>The Cost</Label>
        <h2 className="font-bold mb-4 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          The cost of running memory blind
        </h2>
        <p className="mb-14 max-w-xl" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
          Memory failures don't throw exceptions. They manifest as Ghost Tokens, embedding drift,
          and context noise — silently degrading MAS and response quality at scale.
        </p>

        <div className={`grid md:grid-cols-2 gap-5 transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
          {cards.map(c => (
            <div key={c.title} className="card p-7"
              style={{ borderColor: c.bad ? 'rgba(239,68,68,0.12)' : 'rgba(122,140,0,0.14)' }}>
              <div className="flex items-center gap-2 mb-4">
                {c.bad
                  ? <AlertTriangle size={15} style={{ color: '#B91C1C' }} />
                  : <CheckCircle size={15} style={{ color: 'var(--lime)' }} />}
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text)' }}>{c.title}</h3>
              </div>
              <div className="mb-4">
                <div className="stat-number" style={{ color: c.bad ? '#B91C1C' : 'var(--lime)' }}>
                  {c.metric}
                </div>
                <p className="text-xs mt-1" style={{ color: 'var(--muted)' }}>{c.sub}</p>
              </div>
              <p className="text-sm mb-5 leading-relaxed" style={{ color: 'var(--muted)' }}>{c.desc}</p>
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-mono"
                style={{
                  background: c.bad ? 'rgba(122,140,0,0.08)' : 'rgba(122,140,0,0.10)',
                  border: `1px solid ${c.bad ? 'rgba(122,140,0,0.20)' : 'rgba(122,140,0,0.22)'}`,
                  color: 'var(--lime)',
                }}>
                {c.bad ? <Zap size={11} /> : <CheckCircle size={11} />}
                {c.tag}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// ─── Waitlist CTA ─────────────────────────────────────────────────────────────

// ─── FAQ ──────────────────────────────────────────────────────────────────────

const FAQS = [
  {
    q: 'What exactly is a Ghost Token?',
    a: 'A Ghost Token is a memory retrieved by your RAG or memory pipeline that the LLM never uses when generating its response — injected into context but contributing zero logit influence. Ghost Tokens inflate context size, add inference latency, and crowd out high-attribution memories. Our benchmarks show ~42% of retrieved context in typical production agents is Ghost Tokens.',
  },
  {
    q: 'How does attribution tracing work?',
    a: 'Cortexa instruments your retrieval pipeline to compute a causal attribution score for each memory at inference time. The score represents that memory\'s contribution to the final output — measured by its influence on the logit distribution. High score = that memory shaped the response. When an answer is wrong, the highest-attributing memory is the root cause.',
  },
  {
    q: 'What is the Memory Attribution Score (MAS)?',
    a: 'MAS is the percentage of your retrieved context that has nonzero logit influence. A production agent targeting MAS > 75% is running efficiently — most of what it retrieves actually matters. Below 25%, you\'re in critical context noise territory: high embedding drift, low signal-to-noise, and measurable response degradation.',
  },
  {
    q: 'Does Cortexa replace my memory system?',
    a: 'No. Cortexa wraps your existing store — Mem0, SuperMemory, LangChain, LlamaIndex, or custom. It sits between retrieval and generation. One pip install, zero data migration, no architecture changes. If you can call memory.search(), you can instrument it.',
  },
  {
    q: 'How does the GDPR cascade deletion work?',
    a: 'Cortexa maintains a provenance graph linking source memories to all derived data — embeddings, chunked summaries, cached completions. When a deletion request arrives, cx.delete() walks the graph, cascades removal through every downstream artifact, and generates a cryptographic certificate proving complete erasure. The certificate is auditable and timestamped.',
  },
  {
    q: 'Is Cortexa production-ready?',
    a: 'Cortexa is in early access. We\'re prioritizing teams running agents at scale — 10K+ daily queries, multi-tenant memory, real compliance requirements. If that\'s you, join the waitlist and we\'ll reach out directly.',
  },
]

function FAQ() {
  const [open, setOpen] = useState<number | null>(0)
  const { ref, inView } = useInView(0.08)

  return (
    <section id="faq" className="py-28 px-6" ref={ref}>
      <div className={`max-w-3xl mx-auto transition-opacity duration-700 ${inView ? 'opacity-100' : 'opacity-0'}`}>
        <Label>FAQ</Label>
        <h2 className="font-bold mb-3 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Common questions.
        </h2>
        <p className="mb-12" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
          Technical answers for the engineers evaluating us.
        </p>

        <div style={{ borderTop: '1px solid var(--border)' }}>
          {FAQS.map((faq, i) => {
            const isOpen = open === i
            return (
              <div key={i} style={{ borderBottom: '1px solid var(--border)' }}>
                <button
                  className="w-full flex items-start justify-between gap-6 text-left"
                  style={{ padding: '1.25rem 0', cursor: 'pointer', background: 'none', border: 'none' }}
                  onClick={() => setOpen(isOpen ? null : i)}
                >
                  <span className="text-sm font-semibold" style={{ color: 'var(--text)', lineHeight: 1.5 }}>
                    {faq.q}
                  </span>
                  <span style={{
                    flexShrink: 0,
                    width: 20, height: 20,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: isOpen ? 'var(--lime)' : 'var(--muted)',
                    transition: 'color 0.3s ease',
                    fontSize: '1.1rem', lineHeight: 1, fontWeight: 300,
                    marginTop: 2,
                  }}>
                    {isOpen ? '−' : '+'}
                  </span>
                </button>
                <div style={{
                  display: 'grid',
                  gridTemplateRows: isOpen ? '1fr' : '0fr',
                  transition: 'grid-template-rows 0.45s cubic-bezier(0.625, 0.05, 0, 1)',
                }}>
                  <div style={{ overflow: 'hidden' }}>
                    <p className="text-sm pb-5" style={{ color: 'var(--muted)', lineHeight: 1.75 }}>
                      {faq.a}
                    </p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

// ─── Waitlist CTA ─────────────────────────────────────────────────────────────

const SHEETS_URL = 'https://script.google.com/macros/s/AKfycbzuIb5zHBtc-Y-Qs55ghMBPudpJivVrL7ihCfmbdK-LSE-swU48GGdquzijaKX12s7CVw/exec'

function WaitlistCTA() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  const submit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || loading) return
    setLoading(true); setErr('')
    try {
      await fetch(SHEETS_URL, {
        method: 'POST', mode: 'no-cors',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify({ email: email.trim() }),
      })
      setSubmitted(true)
    } catch {
      setErr('Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }, [email, loading])

  return (
    <section className="py-28 px-6 border-t" style={{ borderColor: 'var(--border)' }}>
      {/* Lime glow above CTA */}
      <div className="relative max-w-2xl mx-auto text-center">
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-40 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse, rgba(122,140,0,0.12) 0%, transparent 70%)', filter: 'blur(30px)' }} />

        <div className="relative z-10">
          <Logo className="logo-img mx-auto mb-8" />

          <h2 className="font-bold mb-4 tracking-tight"
            style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
            Stop debugging blind.
          </h2>
          <p className="mb-3 text-base" style={{ color: 'var(--muted)', lineHeight: 1.7 }}>
            Cortexa is in early access for teams running agents at scale.
            Join the waitlist — we'll reach out when your slot opens.
          </p>
          <p className="mb-10 text-sm font-mono" style={{ color: 'var(--text)' }}>
            or start now:{' '}
            <span style={{ color: 'var(--lime)' }}>pip install cortexos</span>
          </p>

          {submitted ? (
            <div className="flex items-center justify-center gap-2 font-mono" style={{ color: 'var(--lime)' }}>
              <CheckCircle size={18} />
              You're on the list. We'll be in touch.
            </div>
          ) : (
            <form onSubmit={submit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                disabled={loading}
                className="flex-1 px-4 py-3 rounded-xl text-sm font-mono disabled:opacity-50 outline-none transition-all"
                style={{
                  background: 'rgba(28,28,30,0.05)',
                  border: '1px solid var(--border-md)',
                  color: 'var(--text)',
                }}
                onFocus={e => (e.target.style.borderColor = 'rgba(122,140,0,0.5)')}
                onBlur={e => (e.target.style.borderColor = 'var(--border-md)')}
              />
              <button type="submit" className={`btn-primary whitespace-nowrap ${loading ? 'opacity-60 pointer-events-none' : ''}`}>
                {loading ? 'Sending...' : 'Join Waitlist'}
                <ArrowRight size={15} />
              </button>
            </form>
          )}
          {err && <p className="text-xs font-mono mt-3" style={{ color: '#B91C1C' }}>{err}</p>}
        </div>
      </div>
    </section>
  )
}

// ─── Footer ───────────────────────────────────────────────────────────────────

function Footer() {
  return (
    <footer className="py-8 px-6 border-t" style={{ borderColor: 'var(--border)' }}>
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-mono" style={{ color: 'var(--text)' }}>
          <Logo className="logo-img-sm" />
          © 2026 Cortexa
        </div>
        <div className="flex items-center gap-6 text-xs" style={{ color: 'var(--text)' }}>
          <a href="#demo" className="hover:text-[#1C1C1E] transition-colors">How It Works</a>
          <a href="#manifesto" className="hover:text-[#1C1C1E] transition-colors">Manifesto</a>
          <a href="https://github.com/Arunjay4213/Cortexa" target="_blank" rel="noopener noreferrer"
            className="hover:text-[#1C1C1E] transition-colors flex items-center gap-1">
            GitHub <ExternalLink size={11} />
          </a>
        </div>
      </div>
    </footer>
  )
}

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <Nav />
      <Hero />
      <TraceDemo />
      <ThreeQuestions />
      <BeforeAfter />
      <HowItWorks />
      <Manifesto />
      <CostSection />
      <FAQ />
      <WaitlistCTA />
      <Footer />
    </div>
  )
}
