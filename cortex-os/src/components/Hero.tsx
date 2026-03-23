import { motion } from 'motion/react'
import { ArrowRight, ChevronDown } from 'lucide-react'
import NumberFlow from '@number-flow/react'
import { Aurora } from './Aurora'
import { Logo } from './Logo'
import { fadeUp, staggerContainer, hoverScale } from '../lib/motion'

interface HeroProps {
  onOpenDemo: () => void
}

export function Hero({ onOpenDemo }: HeroProps) {
  return (
    <section className="relative min-h-screen flex flex-col items-center justify-center px-6 pt-24 pb-16 text-center overflow-hidden">
      <Aurora />

      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse 80% 70% at 50% 40%, transparent 40%, rgba(28,28,30,0.04) 100%)' }} />

      <motion.div
        className="relative z-10 max-w-5xl mx-auto"
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
      >
        {/* Logo */}
        <motion.div className="flex justify-center mb-10" variants={fadeUp}>
          <Logo className="logo-img" />
        </motion.div>

        {/* Pill badge */}
        <motion.div className="flex justify-center mb-8" variants={fadeUp}>
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-xs font-mono border"
            style={{ background: 'rgba(122,140,0,0.10)', borderColor: 'rgba(122,140,0,0.22)', color: 'var(--lime)' }}>
            <span className="w-1.5 h-1.5 rounded-full bg-lime-500 animate-pulse" />
            Early Access — Now Open
          </span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          className="font-bold leading-[1.08] tracking-tight mb-7"
          style={{ fontSize: 'clamp(2.8rem, 5vw + 1rem, 5.5rem)', color: 'var(--text)' }}
          variants={fadeUp}
        >
          Your agent hallucinated.
          <br />
          <span style={{ color: 'var(--lime)' }}>Which memory caused it?</span>
        </motion.h1>

        {/* Subhead */}
        <motion.p
          className="max-w-2xl mx-auto mb-12 font-light"
          style={{ fontSize: 'clamp(1.05rem, 0.5vw + 0.9rem, 1.25rem)', color: 'var(--muted)', lineHeight: 1.7 }}
          variants={fadeUp}
        >
          Cortexa traces every LLM response back to the memories that shaped it.
          Find the root cause in seconds. Fix it before your users notice.
        </motion.p>

        {/* CTA row */}
        <motion.div className="flex flex-col sm:flex-row items-center justify-center gap-4" variants={fadeUp}>
          <motion.button className="btn-primary" onClick={onOpenDemo} {...hoverScale}>
            See How It Works
            <ArrowRight size={16} />
          </motion.button>
          <motion.button
            className="btn-secondary"
            onClick={() => document.getElementById('manifesto')?.scrollIntoView({ behavior: 'smooth' })}
            {...hoverScale}
          >
            Read the Manifesto
          </motion.button>
        </motion.div>

        {/* Stats row */}
        <motion.div
          className="grid grid-cols-3 gap-6 max-w-xl mx-auto mt-20"
          variants={fadeUp}
        >
          {[
            { n: 3, suffix: 's', label: 'root cause trace' },
            { n: 35, suffix: '%', label: 'context noise reduction' },
            { n: 42, suffix: '%', label: 'Ghost Token recovery' },
          ].map(({ n, suffix, label }) => (
            <div key={label} className="text-center">
              <div className="stat-number" style={{ color: 'var(--lime)' }}>
                <NumberFlow value={n} />{suffix}
              </div>
              <div className="text-xs mt-1.5 font-mono" style={{ color: 'var(--muted)' }}>{label}</div>
            </div>
          ))}
        </motion.div>
      </motion.div>

      {/* Scroll cue */}
      <motion.div
        className="absolute bottom-10 left-1/2 -translate-x-1/2"
        style={{ color: 'var(--muted)', opacity: 0.4 }}
        animate={{ y: [0, 6, 0] }}
        transition={{ duration: 1.8, ease: 'easeInOut', repeat: Infinity }}
      >
        <ChevronDown size={20} />
      </motion.div>
    </section>
  )
}
