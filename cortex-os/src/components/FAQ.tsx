import { useState } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { fadeIn } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

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

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="py-28 px-6">
      <motion.div
        className="max-w-3xl mx-auto"
        variants={fadeIn}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.08 }}
      >
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
                  <motion.span
                    style={{
                      flexShrink: 0,
                      width: 20, height: 20,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: isOpen ? 'var(--lime)' : 'var(--muted)',
                      fontSize: '1.1rem', lineHeight: 1, fontWeight: 300,
                      marginTop: 2,
                    }}
                    animate={{ rotate: isOpen ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    +
                  </motion.span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      style={{ overflow: 'hidden' }}
                    >
                      <p className="text-sm pb-5" style={{ color: 'var(--muted)', lineHeight: 1.75 }}>
                        {faq.a}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            )
          })}
        </div>
      </motion.div>
    </section>
  )
}
