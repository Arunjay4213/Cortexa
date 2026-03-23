import { motion } from 'motion/react'
import {
  TrendingUp, Activity, Shield, XCircle, Clock,
  AlertTriangle, FileCheck,
} from 'lucide-react'
import { ProvenanceGraph } from './ProvenanceGraph'
import { fadeUp, staggerContainer } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

export function ThreeQuestions() {
  return (
    <section className="py-28 px-6">
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

        <motion.div
          className="grid md:grid-cols-3 gap-5"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.08 }}
        >
          {/* Card 1: Attribution Density */}
          <motion.div className="card p-7" variants={fadeUp}>
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
          </motion.div>

          {/* Card 2: Health */}
          <motion.div className="card p-7" variants={fadeUp}>
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
          </motion.div>

          {/* Card 3: Compliance */}
          <motion.div className="card p-7" variants={fadeUp}>
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
          </motion.div>
        </motion.div>

        {/* MAS Benchmark callout */}
        <motion.div
          className="mt-10 rounded-2xl p-7"
          style={{ background: 'rgba(122,140,0,0.06)', border: '1px solid rgba(122,140,0,0.2)' }}
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.7 }}
        >
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
        </motion.div>
      </div>
    </section>
  )
}
