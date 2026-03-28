import { useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'motion/react'
import { X, ShieldCheck } from 'lucide-react'

const SHEETS_URL = 'https://script.google.com/macros/s/AKfycbzuIb5zHBtc-Y-Qs55ghMBPudpJivVrL7ihCfmbdK-LSE-swU48GGdquzijaKX12s7CVw/exec'

interface ModalProps {
  open: boolean
  onClose: () => void
}

export function VideoModal({ open, onClose }: ModalProps) {
  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.8)', backdropFilter: 'blur(4px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.95, opacity: 0 }}
            className="relative w-full max-w-5xl rounded-2xl overflow-hidden"
            style={{ aspectRatio: '16/9', background: '#000', border: '1px solid var(--border)' }}
            onClick={e => e.stopPropagation()}
          >
            <button
              onClick={onClose}
              className="absolute top-4 right-4 z-10 p-2 rounded-full transition-colors"
              style={{ background: 'rgba(255,255,255,0.1)', color: '#fff' }}
            >
              <X size={20} />
            </button>
            <div className="w-full h-full flex items-center justify-center">
              <p className="text-sm font-mono" style={{ color: 'rgba(255,255,255,0.5)' }}>Demo video coming soon</p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

export function EarlyAccessModal({ open, onClose }: ModalProps) {
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
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={onClose}
        >
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 20, opacity: 0 }}
            className="w-full max-w-md rounded-2xl p-8 shadow-2xl"
            style={{ background: '#fff', border: '1px solid var(--border)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center mb-6">
              <h3 className="text-2xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Space Grotesk', sans-serif" }}>
                Early Access
              </h3>
              <button onClick={onClose} className="transition-colors" style={{ color: 'var(--muted)' }}>
                <X size={24} />
              </button>
            </div>

            {!submitted ? (
              <form onSubmit={submit} className="space-y-4">
                <p className="text-sm mb-6" style={{ color: 'var(--muted)' }}>
                  Join the waitlist to get early access to Cortexa. We'll reach out when your slot opens.
                </p>
                <div>
                  <label className="block text-[10px] font-bold uppercase tracking-widest mb-2"
                    style={{ color: 'var(--muted)' }}>
                    Work Email
                  </label>
                  <input
                    required
                    type="email"
                    placeholder="name@company.com"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    disabled={loading}
                    className="w-full rounded-xl px-4 py-3 text-sm font-mono outline-none transition-all disabled:opacity-50"
                    style={{
                      background: 'var(--bg)',
                      border: '1px solid var(--border-md)',
                      color: 'var(--text)',
                    }}
                    onFocus={e => (e.target.style.borderColor = 'rgba(122,140,0,0.5)')}
                    onBlur={e => (e.target.style.borderColor = 'var(--border-md)')}
                  />
                </div>
                <button
                  type="submit"
                  className={`w-full py-3.5 rounded-xl font-bold transition-colors ${loading ? 'opacity-60 pointer-events-none' : ''}`}
                  style={{
                    background: 'var(--lime)',
                    color: '#fff',
                    fontFamily: "'Space Grotesk', sans-serif",
                  }}
                >
                  {loading ? 'Sending...' : 'Join Waitlist'}
                </button>
                {err && <p className="text-xs font-mono" style={{ color: '#B91C1C' }}>{err}</p>}
              </form>
            ) : (
              <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} className="text-center py-8 space-y-4">
                <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4"
                  style={{ background: 'var(--lime-dim)', color: 'var(--lime)' }}>
                  <ShieldCheck size={32} />
                </div>
                <h4 className="text-xl font-bold" style={{ color: 'var(--text)', fontFamily: "'Space Grotesk', sans-serif" }}>
                  You're on the list!
                </h4>
                <p style={{ color: 'var(--muted)' }}>We'll reach out as soon as a spot opens up.</p>
                <button onClick={onClose} className="font-bold pt-4 hover:underline" style={{ color: 'var(--lime)' }}>
                  Back to site
                </button>
              </motion.div>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
