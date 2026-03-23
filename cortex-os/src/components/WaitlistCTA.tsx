import { useState, useCallback } from 'react'
import { motion } from 'motion/react'
import { ArrowRight, CheckCircle } from 'lucide-react'
import { Logo } from './Logo'
import { fadeUp, staggerContainer, hoverScale } from '../lib/motion'

const SHEETS_URL = 'https://script.google.com/macros/s/AKfycbzuIb5zHBtc-Y-Qs55ghMBPudpJivVrL7ihCfmbdK-LSE-swU48GGdquzijaKX12s7CVw/exec'

export function WaitlistCTA() {
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
      <div className="relative max-w-2xl mx-auto text-center">
        <div className="absolute -top-24 left-1/2 -translate-x-1/2 w-96 h-40 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse, rgba(122,140,0,0.12) 0%, transparent 70%)', filter: 'blur(30px)' }} />

        <motion.div
          className="relative z-10"
          variants={staggerContainer}
          initial="hidden"
          whileInView="visible"
          viewport={{ once: true, amount: 0.3 }}
        >
          <motion.div variants={fadeUp}>
            <Logo className="logo-img mx-auto mb-8" />
          </motion.div>

          <motion.h2
            className="font-bold mb-4 tracking-tight"
            style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}
            variants={fadeUp}
          >
            Stop debugging blind.
          </motion.h2>
          <motion.p className="mb-3 text-base" style={{ color: 'var(--muted)', lineHeight: 1.7 }} variants={fadeUp}>
            Cortexa is in early access for teams running agents at scale.
            Join the waitlist — we'll reach out when your slot opens.
          </motion.p>
          <motion.p className="mb-10 text-sm font-mono" style={{ color: 'var(--text)' }} variants={fadeUp}>
            or start now:{' '}
            <span style={{ color: 'var(--lime)' }}>pip install cortexos</span>
          </motion.p>

          <motion.div variants={fadeUp}>
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
                <motion.button
                  type="submit"
                  className={`btn-primary whitespace-nowrap ${loading ? 'opacity-60 pointer-events-none' : ''}`}
                  {...hoverScale}
                >
                  {loading ? 'Sending...' : 'Join Waitlist'}
                  <ArrowRight size={15} />
                </motion.button>
              </form>
            )}
            {err && <p className="text-xs font-mono mt-3" style={{ color: '#B91C1C' }}>{err}</p>}
          </motion.div>
        </motion.div>
      </div>
    </section>
  )
}
