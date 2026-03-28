import { useState, useEffect } from 'react'
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
import { DocsPage } from './components/DocsPage'

export default function App() {
  const [videoOpen, setVideoOpen] = useState(false)
  const [earlyAccessOpen, setEarlyAccessOpen] = useState(false)
  const [path, setPath] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    const redirectPath = params.get('p')
    if (redirectPath) {
      window.history.replaceState(null, '', redirectPath)
      return redirectPath
    }
    return window.location.pathname
  })

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  if (path === '/docs') {
    return <DocsPage />
  }

  return (
    <div style={{ minHeight: '100vh' }}>
      <Navbar onOpenEarlyAccess={() => setEarlyAccessOpen(true)} />

      {/* Dark hero section */}
      <Hero
        onOpenDemo={() => document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' })}
      />

      {/* Light sections */}
      <div data-theme="light" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
        <TraceDemo />
        <ThreeQuestions />
        <BeforeAfter />
        <HowItWorks />
        <Manifesto />
        <CostSection />
        <FAQ />
        <WaitlistCTA />
        <Footer />
      </div>

      <VideoModal open={videoOpen} onClose={() => setVideoOpen(false)} />
      <EarlyAccessModal open={earlyAccessOpen} onClose={() => setEarlyAccessOpen(false)} />
    </div>
  )
}
