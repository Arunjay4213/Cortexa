import { motion } from 'motion/react'
import { fadeIn } from '../lib/motion'

function Label({ children }: { children: string }) {
  return (
    <div className="section-label">
      <span>{children}</span>
    </div>
  )
}

export function Manifesto() {
  return (
    <section id="manifesto" className="py-28 px-6">
      <motion.div
        className="max-w-3xl mx-auto"
        variants={fadeIn}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.08 }}
      >
        <Label>Manifesto</Label>

        <h2 className="font-bold mb-12 tracking-tight"
          style={{ fontSize: 'clamp(1.8rem, 2.5vw + 0.8rem, 2.8rem)', color: 'var(--text)' }}>
          Memory without observability is liability.
        </h2>

        <div className="space-y-6 text-base leading-[1.75]" style={{ color: 'rgba(28,28,30,0.70)' }}>
          <p>
            Every AI engineering team is building memory into their agents. Persistent context,
            user history, retrieved knowledge — it makes agents smarter, more personalized, more useful.
          </p>
          <p>But nobody is watching the memories.</p>
          <p style={{ color: 'var(--text)', fontWeight: 500 }}>
            When your agent gives a wrong answer, you can't tell which memory caused it.
            When your token bill spikes, you can't tell which memories are worth paying for.
            When a user requests deletion, you can't prove you got everything.
          </p>
          <p>
            Memory systems today are black boxes. Mem0, Zep, custom RAG stores — they all solve
            the same problem: <em>how to store and retrieve memories</em>. None of them solve
            the next one: <em>how to know if those memories are helping or hurting</em>.
          </p>
          <p>This is the observability gap.</p>
          <p>
            Database engineers solved this decades ago. You wouldn't run Postgres without
            <code className="px-1.5 py-0.5 rounded text-sm mx-1 font-mono"
              style={{ background: 'rgba(122,140,0,0.12)', color: 'var(--lime)' }}>
              EXPLAIN ANALYZE
            </code>.
            You wouldn't ship an API without distributed tracing. You wouldn't run a service
            without metrics and alerting.
          </p>
          <p>
            Yet every AI team is running memory systems blind. Injecting hundreds of memories
            into every prompt. Paying for tokens they don't need. Trusting data they haven't
            verified. Hoping nothing contradicts.
          </p>
          <p className="text-lg font-semibold" style={{ color: 'var(--text)' }}>
            Cortexa is the observability layer for agent memory.
          </p>
          <p>
            For every response, we trace which memories influenced which claims. We score their
            contribution. We find contradictions, stale data, and coverage gaps. We show you
            which memories earn their tokens and which are dead weight.
          </p>
          <p>We don't replace your memory system. We make it accountable.</p>

          <blockquote className="my-10 pl-5 py-1 border-l-2" style={{ borderColor: 'var(--lime)' }}>
            <p className="font-mono text-sm" style={{ color: 'var(--lime)' }}>
              "If you can't measure it, you can't improve it. If you can't trace it, you can't
              trust it. If you can't prove deletion, you can't comply."
            </p>
          </blockquote>

          <p className="text-sm" style={{ color: 'rgba(28,28,30,0.35)' }}>
            We're building for teams running agents at scale — 10K queries/day, hundreds of
            memories per user, real compliance requirements. If that's you, we'd love to talk.
          </p>
        </div>
      </motion.div>
    </section>
  )
}
