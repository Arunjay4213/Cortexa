import { motion } from 'motion/react'
import { Terminal, Github } from 'lucide-react'
import { useScrolled } from '../hooks/useScrolled'
import { Logo } from './Logo'
import { hoverScale } from '../lib/motion'

interface NavbarProps {
  onOpenEarlyAccess: () => void
}

export function Navbar({ onOpenEarlyAccess }: NavbarProps) {
  const scrolled = useScrolled()
  const navLink = { color: 'var(--text)' } as const

  return (
    <nav className={`nav-base ${scrolled ? 'nav-scrolled' : ''}`}>
      <div className="flex items-center gap-6">
        <Logo className="logo-img-nav" />
        <div className="hidden sm:flex items-center gap-5">
          {[
            { href: '#demo',         label: 'Demo' },
            { href: '#how-it-works', label: 'How It Works' },
            { href: '#manifesto',    label: 'Manifesto' },
            { href: '#faq',          label: 'FAQ' },
          ].map(({ href, label }) => (
            <a key={href} href={href} className="text-sm font-medium transition-colors" style={navLink}>
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
          className="flex items-center transition-colors"
          style={navLink}
        >
          <Github size={16} />
        </a>
        <motion.button
          className="btn-primary text-xs px-4 py-2"
          onClick={onOpenEarlyAccess}
          {...hoverScale}
        >
          <Terminal size={13} />
          Early Access
        </motion.button>
      </div>
    </nav>
  )
}
