import { motion } from 'motion/react'
import { ArrowLeft } from 'lucide-react'
import { Logo } from './Logo'
import { fadeUp, staggerContainer } from '../lib/motion'

export function ManifestoPage() {
  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      {/* Top bar */}
      <header
        className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between"
        style={{
          height: 68,
          padding: '0 clamp(1.5rem, 4vw, 4rem)',
          background: 'rgba(232,227,213,0.88)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
          borderBottom: '1px solid var(--border)',
        }}
      >
        <div className="flex items-center gap-5">
          <a
            href="/"
            className="flex items-center gap-2 text-sm font-medium transition-opacity hover:opacity-70"
            style={{ color: 'var(--muted)' }}
          >
            <ArrowLeft size={14} strokeWidth={1.5} />
            <Logo className="logo-img-sm" />
          </a>
          <div style={{ width: 1, height: 24, background: 'var(--border-md)' }} />
          <span className="text-base font-semibold">Manifesto</span>
        </div>
      </header>

      {/* Content */}
      <motion.main
        className="max-w-2xl mx-auto px-6 py-10"
        style={{ paddingTop: 120 }}
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
      >
        <motion.div className="section-label mb-8" variants={fadeUp}>
          <span>Manifesto</span>
        </motion.div>

        <motion.h1
          className="font-bold tracking-tight mb-6"
          style={{ fontSize: 'clamp(2rem, 3vw + 1rem, 3rem)', lineHeight: 1.15 }}
          variants={fadeUp}
        >
          Memory without observability is liability.
        </motion.h1>

        <motion.div
          className="h-px w-16 mb-12"
          style={{ background: 'var(--lime)' }}
          variants={fadeUp}
        />

        <motion.article
          className="space-y-7 text-base leading-[1.85]"
          style={{ color: 'rgba(28,28,30,0.70)' }}
          variants={staggerContainer}
          initial="hidden"
          animate="visible"
        >
          <motion.p variants={fadeUp}>
            Every AI engineering team is building memory into their agents. Persistent context,
            user history, retrieved knowledge — it makes agents smarter, more personalized, more useful.
          </motion.p>

          <motion.p variants={fadeUp} style={{ color: 'var(--text)', fontWeight: 600, fontSize: '1.1rem' }}>
            But nobody is watching the memories.
          </motion.p>

          <motion.p variants={fadeUp} style={{ color: 'var(--text)', fontWeight: 500 }}>
            When your agent gives a wrong answer, you can't tell which memory caused it.
            When your token bill spikes, you can't tell which memories are worth paying for.
            When a user requests deletion, you can't prove you got everything.
          </motion.p>

          <motion.p variants={fadeUp}>
            Memory systems today are black boxes. Mem0, Zep, custom RAG stores — they all solve
            the same problem: <em>how to store and retrieve memories</em>. None of them solve
            the next one: <em>how to know if those memories are helping or hurting</em>.
          </motion.p>

          <motion.p variants={fadeUp} style={{ color: 'var(--text)', fontWeight: 600, fontSize: '1.1rem' }}>
            This is the observability gap.
          </motion.p>

          <motion.p variants={fadeUp}>
            Database engineers solved this decades ago. You wouldn't run Postgres without{' '}
            <code
              className="px-1.5 py-0.5 rounded text-sm mx-0.5 font-mono"
              style={{ background: 'rgba(122,140,0,0.12)', color: 'var(--lime)' }}
            >
              EXPLAIN ANALYZE
            </code>
            . You wouldn't ship an API without distributed tracing. You wouldn't run a service
            without metrics and alerting.
          </motion.p>

          <motion.p variants={fadeUp}>
            Yet every AI team is running memory systems blind. Injecting hundreds of memories
            into every prompt. Paying for tokens they don't need. Trusting data they haven't
            verified. Hoping nothing contradicts.
          </motion.p>

          <motion.div variants={fadeUp}>
            <div className="my-4 h-px" style={{ background: 'var(--border)' }} />
          </motion.div>

          <motion.p
            className="text-xl font-bold"
            style={{ color: 'var(--text)', lineHeight: 1.4 }}
            variants={fadeUp}
          >
            Cortexa is the observability layer for agent memory.
          </motion.p>

          <motion.p variants={fadeUp}>
            For every response, we trace which memories influenced which claims. We score their
            contribution. We find contradictions, stale data, and coverage gaps. We show you
            which memories earn their tokens and which are dead weight.
          </motion.p>

          <motion.p variants={fadeUp} style={{ color: 'var(--text)', fontWeight: 500 }}>
            We don't replace your memory system. We make it accountable.
          </motion.p>

          <motion.blockquote
            className="my-12 pl-6 py-4 border-l-2"
            style={{ borderColor: 'var(--lime)', background: 'rgba(122,140,0,0.04)', borderRadius: '0 12px 12px 0' }}
            variants={fadeUp}
          >
            <p className="font-mono text-sm italic" style={{ color: 'var(--lime)', lineHeight: 1.8 }}>
              "If you can't measure it, you can't improve it. If you can't trace it, you can't
              trust it. If you can't prove deletion, you can't comply."
            </p>
          </motion.blockquote>

          <motion.p className="text-sm" style={{ color: 'rgba(28,28,30,0.40)' }} variants={fadeUp}>
            We're building for teams running agents at scale — 10K queries/day, hundreds of
            memories per user, real compliance requirements. If that's you, we'd love to talk.
          </motion.p>
        </motion.article>

        {/* Footer spacer */}
        <div className="h-20" />
      </motion.main>
    </div>
  )
}
