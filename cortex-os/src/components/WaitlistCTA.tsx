import { motion } from 'motion/react'
import { fadeUp, staggerContainer, hoverScale } from '../lib/motion'

interface WaitlistCTAProps {
  onOpenEarlyAccess: () => void
}

export function WaitlistCTA({ onOpenEarlyAccess }: WaitlistCTAProps) {
  return (
    <section className="py-28 px-6">
      <motion.div
        className="relative max-w-5xl mx-auto rounded-3xl overflow-hidden text-center"
        style={{ background: '#1c1917' }}
        variants={staggerContainer}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.3 }}
      >
        <div className="absolute inset-0 pointer-events-none"
          style={{ background: 'linear-gradient(135deg, rgba(122,140,0,0.10) 0%, transparent 60%)' }} />

        <div className="relative z-10 px-8 py-16 md:py-24 space-y-6">
          <motion.h2
            className="font-bold tracking-tight text-white"
            style={{ fontSize: 'clamp(2rem, 4vw + 0.5rem, 3.5rem)', fontFamily: "'Space Grotesk', sans-serif" }}
            variants={fadeUp}
          >
            Stop guessing.{' '}
            <span style={{ color: '#c6ef00' }}>Start tracing.</span>
          </motion.h2>

          <motion.p
            className="text-lg max-w-xl mx-auto"
            style={{ color: 'rgba(255,255,255,0.55)' }}
            variants={fadeUp}
          >
            Deploy Cortexa's memory observability layer in under 5 minutes.
            Compatible with all major LLM providers.
          </motion.p>

          <motion.div className="pt-4" variants={fadeUp}>
            <motion.button
              onClick={onOpenEarlyAccess}
              className="px-10 py-4 rounded-full font-bold text-lg transition-all"
              style={{
                background: '#c6ef00',
                color: '#1c1917',
                fontFamily: "'Space Grotesk', sans-serif",
                boxShadow: '0 0 20px rgba(198,239,0,0.3)',
              }}
              {...hoverScale}
            >
              Request Early Access
            </motion.button>
          </motion.div>
        </div>
      </motion.div>
    </section>
  )
}
