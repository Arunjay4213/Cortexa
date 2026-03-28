import { useState, useEffect, useRef } from 'react'
import { motion } from 'motion/react'
import { Terminal, Github } from 'lucide-react'
import { Logo } from './Logo'
import { hoverScale } from '../lib/motion'

type NavTheme = 'dark' | 'light'

interface NavbarProps {
  onOpenEarlyAccess: () => void
}

export function Navbar({ onOpenEarlyAccess }: NavbarProps) {
  const [navTheme, setNavTheme] = useState<NavTheme>('dark')
  const [scrolled, setScrolled] = useState(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  useEffect(() => {
    const sections = document.querySelectorAll<HTMLElement>('[data-theme]')
    if (sections.length === 0) return

    observerRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const theme = entry.target.getAttribute('data-theme') as NavTheme
            if (theme) setNavTheme(theme)
          }
        }
      },
      {
        rootMargin: '-1px 0px -95% 0px',
        threshold: 0,
      }
    )

    sections.forEach((section) => observerRef.current!.observe(section))

    return () => {
      observerRef.current?.disconnect()
      observerRef.current = null
    }
  }, [])

  const isDark = navTheme === 'dark'

  return (
    <nav
      className={`fixed top-0 w-full z-50 transition-all duration-500 ease-in-out ${
        isDark
          ? scrolled
            ? 'backdrop-blur-xl border-b border-white/5'
            : 'bg-transparent border-b border-transparent'
          : scrolled
            ? 'backdrop-blur-md border-b shadow-sm'
            : 'bg-transparent border-b border-transparent'
      } ${scrolled ? 'py-2' : 'py-3'}`}
      style={{
        background: isDark
          ? scrolled ? 'rgba(24,24,27,0.8)' : 'transparent'
          : scrolled ? 'rgba(232,227,213,0.88)' : 'transparent',
        borderColor: isDark ? undefined : scrolled ? 'var(--border)' : 'transparent',
      }}
    >
      <div className="flex justify-between items-center px-8 max-w-screen-2xl mx-auto">
        <div className="flex items-center gap-6">
          {isDark ? (
            <a
              href="/"
              className="text-2xl font-bold tracking-tighter text-zinc-50 transition-colors duration-500"
              style={{ fontFamily: "'Space Grotesk', sans-serif" }}
            >
              Cortexa
            </a>
          ) : (
            <Logo className="logo-img-nav" />
          )}
          <div className="hidden sm:flex items-center gap-5">
            {[
              { href: '#demo', label: 'Demo' },
              { href: '#how-it-works', label: 'How It Works' },
              { href: '/manifesto', label: 'Manifesto' },
              { href: '#faq', label: 'FAQ' },
              { href: '/docs', label: 'Docs' },
            ].map(({ href, label }) => (
              <a
                key={href}
                href={href}
                className="text-sm font-medium transition-colors duration-500"
                style={{
                  color: isDark ? '#a1a1aa' : 'var(--text)',
                  fontFamily: isDark ? "'Space Grotesk', sans-serif" : undefined,
                }}
                onMouseEnter={e => (e.currentTarget.style.color = isDark ? '#c6ef00' : 'var(--lime)')}
                onMouseLeave={e => (e.currentTarget.style.color = isDark ? '#a1a1aa' : 'var(--text)')}
              >
                {label}
              </a>
            ))}
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-4">
          <a
            href="https://github.com/Arunjay4213/Cortexa"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center transition-colors duration-500"
            style={{ color: isDark ? '#fafafa' : 'var(--text)' }}
          >
            <Github size={16} />
          </a>
          <motion.button
            className="text-xs px-4 py-2 font-semibold rounded-lg flex items-center gap-2 transition-all duration-500"
            onClick={onOpenEarlyAccess}
            style={{
              background: isDark ? '#c6ef00' : 'var(--lime)',
              color: isDark ? '#0a0a0a' : '#ffffff',
              fontFamily: isDark ? "'Space Grotesk', sans-serif" : undefined,
            }}
            {...hoverScale}
          >
            <Terminal size={13} />
            Early Access
          </motion.button>
        </div>
      </div>
    </nav>
  )
}
