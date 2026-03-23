import { motion } from 'motion/react'
import {
  CheckCircle, XCircle, Clock, DollarSign, TrendingUp,
  Shield, Zap, FileCheck,
} from 'lucide-react'
import { fadeUp, staggerContainer } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

export function BeforeAfter() {
  return (
    <section className="py-28 px-6">
      <div className="max-w-5xl mx-auto">
        <Label>The Difference</Label>
        <h2 className="font-bold mb-14 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Before and after Cortexa
        </h2>

        <motion.div
          className="grid md:grid-cols-2 gap-6"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.08 }}
        >
          <motion.div className="card p-7" style={{ borderColor: 'rgba(239,68,68,0.15)', background: 'rgba(239,68,68,0.03)' }} variants={fadeUp}>
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
          </motion.div>

          <motion.div className="card p-7" style={{ borderColor: 'rgba(122,140,0,0.15)', background: 'rgba(122,140,0,0.02)' }} variants={fadeUp}>
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
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
