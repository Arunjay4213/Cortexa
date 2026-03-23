import { useState } from 'react'
import { Navbar } from './components/Navbar'
import { Hero } from './components/Hero'
import { TraceDemo } from './components/TraceDemo'
import { ThreeQuestions } from './components/ThreeQuestions'
import { BeforeAfter } from './components/BeforeAfter'
import { HowItWorks } from './components/HowItWorks'
import { Manifesto } from './components/Manifesto'
import { CostSection } from './components/CostSection'
import { FAQ } from './components/FAQ'
import { WaitlistCTA } from './components/WaitlistCTA'
import { Footer } from './components/Footer'
import { VideoModal, EarlyAccessModal } from './components/Modals'

export default function App() {
  const [videoOpen, setVideoOpen] = useState(false)
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', color: 'var(--text)' }}>
      <Navbar onOpenEarlyAccess={() => setEarlyAccessOpen(true)} />
      <Hero onOpenDemo={() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })} />
      <TraceDemo />
      <ThreeQuestions />
      <BeforeAfter />
      <HowItWorks />
      <Manifesto />
      <CostSection />
      <FAQ />
      <WaitlistCTA />
      <Footer />

      <VideoModal open={videoOpen} onClose={() => setVideoOpen(false)} />
      <EarlyAccessModal open={earlyAccessOpen} onClose={() => setEarlyAccessOpen(false)} />
    </div>
  )
}
