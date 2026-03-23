import { useRef } from 'react'
import { motion, AnimatePresence, useInView } from 'motion/react'
import {
  Search, Zap, AlertTriangle,
  CheckCircle, XCircle, Clock, Activity,
} from 'lucide-react'
import { useStagger } from '../hooks/useStagger'
import { fadeUp, slideLeft } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

export function TraceDemo() {
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, amount: 0.1 })
  const step = useStagger(inView, 5, 550)

  const pulseRed = {
    animate: {
      boxShadow: [
        '0 0 0 0 rgba(239,68,68,0)',
        '0 0 24px 2px rgba(239,68,68,0.35)',
        '0 0 0 0 rgba(239,68,68,0)',
      ],
    },
    transition: { duration: 2.4, ease: 'easeInOut' as const, repeat: Infinity },
  }

  const pulseLime = {
    animate: {
      boxShadow: [
        '0 0 0 0 rgba(122,140,0,0)',
        '0 0 28px 4px rgba(122,140,0,0.25)',
        '0 0 0 0 rgba(122,140,0,0)',
      ],
    },
    transition: { duration: 2.4, ease: 'easeInOut' as const, repeat: Infinity },
  }

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
            <AnimatePresence>
              {/* Step 1 — wrong answer */}
              {step >= 1 && (
                <motion.div
                  key="step1"
                  variants={fadeUp}
                  initial="hidden"
                  animate="visible"
                >
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
                </motion.div>
              )}

              {/* Step 2 — attribution trace */}
              {step >= 2 && (
                <motion.div
                  key="step2"
                  variants={fadeUp}
                  initial="hidden"
                  animate="visible"
                >
                  <div className="flex items-center gap-2 text-xs mb-3" style={{ color: 'var(--muted)', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                    <Search size={12} /> ATTRIBUTION TRACE — culprit found
                  </div>
                  <motion.div
                    className="rounded-xl p-4"
                    style={{ background: 'var(--red-dim)', border: '1px solid rgba(239,68,68,0.22)' }}
                    {...pulseRed}
                  >
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
                  </motion.div>
                </motion.div>
              )}

              {/* Step 3 — correct memory was there, just buried */}
              {step >= 3 && (
                <motion.div
                  key="step3"
                  variants={slideLeft}
                  initial="hidden"
                  animate="visible"
                >
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
                </motion.div>
              )}

              {/* Step 4 — fix */}
              {step >= 4 && (
                <motion.div
                  key="step4"
                  variants={fadeUp}
                  initial="hidden"
                  animate="visible"
                >
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
                </motion.div>
              )}

              {/* Step 5 — corrected + time */}
              {step >= 5 && (
                <motion.div
                  key="step5"
                  variants={fadeUp}
                  initial="hidden"
                  animate="visible"
                >
                  <div className="flex items-center gap-2 text-xs mb-2" style={{ color: 'var(--lime)' }}>
                    <CheckCircle size={13} /> CORRECTED RESPONSE
                  </div>
                  <motion.div
                    className="rounded-xl p-4"
                    style={{ background: 'var(--lime-dim)', border: '1px solid rgba(122,140,0,0.22)' }}
                    {...pulseLime}
                  >
                    <p style={{ color: 'var(--text)' }}>"Your order will arrive in <strong>5–7 business days</strong>. Standard shipping is free over $35!"</p>
                  </motion.div>
                  <div className="flex items-center justify-between mt-4 pt-4 border-t" style={{ borderColor: 'var(--border)' }}>
                    <div className="flex items-center gap-2">
                      <Activity size={14} style={{ color: 'var(--lime)' }} />
                      <span className="text-xs" style={{ color: 'var(--lime)' }}>Root cause found in <strong>2.3 seconds</strong></span>
                    </div>
                    <span className="text-xs" style={{ color: 'var(--muted)' }}>previously: 45 min of log archaeology</span>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  )
}
