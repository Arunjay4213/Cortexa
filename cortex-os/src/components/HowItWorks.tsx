import { motion } from 'motion/react'
import { Layers, Zap, Eye } from 'lucide-react'
import { fadeUp, staggerContainer } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

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

export function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 px-6">
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

        <motion.div
          className="grid md:grid-cols-3 gap-5 mb-14"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.08 }}
        >
          {steps.map(s => (
            <motion.div key={s.n} className="card p-7" variants={fadeUp}>
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
            </motion.div>
          ))}
        </motion.div>

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
