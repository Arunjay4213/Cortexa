import { motion } from 'motion/react'
import { AlertTriangle, CheckCircle, Zap } from 'lucide-react'
import { fadeUp, staggerContainer } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

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

export function CostSection() {
  return (
    <section className="py-28 px-6">
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

        <motion.div
          className="grid md:grid-cols-2 gap-5"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.08 }}
        >
          {cards.map(c => (
            <motion.div key={c.title} className="card p-7" variants={fadeUp}
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
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  )
}
