import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X, ArrowRight, CheckCircle } from 'lucide-react'

const SHEETS_URL = 'https://script.google.com/macros/s/AKfycbzuIb5zHBtc-Y-Qs55ghMBPudpJivVrL7ihCfmbdK-LSE-swU48GGdquzijaKX12s7CVw/exec'

const backdrop = {
  hidden: { opacity: 0 },
  visible: { opacity: 1 },
  exit: { opacity: 0 },
}

const modal = {
  hidden: { opacity: 0, scale: 0.95, y: 20 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { duration: 0.3, ease: [0.16, 1, 0.3, 1] as const } },
  exit: { opacity: 0, scale: 0.95, y: 20, transition: { duration: 0.2 } },
}

interface ModalShellProps {
  open: boolean
  onClose: () => void
  children: React.ReactNode
}

function ModalShell({ open, onClose, children }: ModalShellProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 flex items-center justify-center p-4"
          style={{ zIndex: 1000 }}
          variants={backdrop}
          initial="hidden"
          animate="visible"
          exit="exit"
        >
          <motion.div
            className="absolute inset-0"
            style={{ background: 'rgba(28,28,30,0.4)', backdropFilter: 'blur(4px)' }}
            onClick={onClose}
          />
          <motion.div
            className="relative w-full max-w-lg rounded-2xl p-8"
            style={{
              background: 'var(--bg-card)',
              border: '1px solid var(--border-md)',
              boxShadow: '0 25px 50px rgba(28,28,30,0.15)',
            }}
            variants={modal}
            initial="hidden"
            animate="visible"
            exit="exit"
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 p-1 rounded-lg transition-colors"
              style={{ color: 'var(--muted)' }}
              onMouseEnter={e => (e.currentTarget.style.color = 'var(--text)')}
              onMouseLeave={e => (e.currentTarget.style.color = 'var(--muted)')}
            >
              <X size={18} />
            </button>
            {children}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

interface VideoModalProps {
  open: boolean
  onClose: () => void
}

export function VideoModal({ open, onClose }: VideoModalProps) {
  return (
    <ModalShell open={open} onClose={onClose}>
      <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text)' }}>
        See Cortexa in Action
      </h3>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
        Watch how Cortexa traces a hallucination back to its root memory in seconds.
      </p>
      <div className="rounded-xl overflow-hidden" style={{ background: 'rgba(28,28,30,0.06)', border: '1px solid var(--border)', aspectRatio: '16/9' }}>
        <div className="w-full h-full flex items-center justify-center">
          <p className="text-sm font-mono" style={{ color: 'var(--muted)' }}>Demo video coming soon</p>
        </div>
      </div>
    </ModalShell>
  )
}

interface EarlyAccessModalProps {
  open: boolean
  onClose: () => void
}

export function EarlyAccessModal({ open, onClose }: EarlyAccessModalProps) {
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
    <ModalShell open={open} onClose={onClose}>
      <h3 className="text-lg font-bold mb-2" style={{ color: 'var(--text)' }}>
        Get Early Access
      </h3>
      <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
        Join the waitlist for teams running agents at scale. We'll reach out when your slot opens.
      </p>

      {submitted ? (
        <div className="flex items-center gap-2 font-mono text-sm" style={{ color: 'var(--lime)' }}>
          <CheckCircle size={18} />
          You're on the list. We'll be in touch.
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <input
            type="email"
            placeholder="you@company.com"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            disabled={loading}
            className="w-full px-4 py-3 rounded-xl text-sm font-mono disabled:opacity-50 outline-none transition-all"
            style={{
              background: 'rgba(28,28,30,0.05)',
              border: '1px solid var(--border-md)',
              color: 'var(--text)',
            }}
            onFocus={e => (e.target.style.borderColor = 'rgba(122,140,0,0.5)')}
            onBlur={e => (e.target.style.borderColor = 'var(--border-md)')}
          />
          <button
            type="submit"
            className={`btn-primary w-full justify-center ${loading ? 'opacity-60 pointer-events-none' : ''}`}
          >
            {loading ? 'Sending...' : 'Join Waitlist'}
            <ArrowRight size={15} />
          </button>
          {err && <p className="text-xs font-mono" style={{ color: '#B91C1C' }}>{err}</p>}
        </form>
      )}
    </ModalShell>
  )
}
