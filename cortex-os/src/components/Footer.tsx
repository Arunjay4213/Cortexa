import { ExternalLink } from 'lucide-react'
import { Logo } from './Logo'

export function Footer() {
  return (
    <footer className="py-8 px-6 border-t" style={{ borderColor: 'var(--border)' }}>
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-2 text-sm font-mono" style={{ color: 'var(--text)' }}>
          <Logo className="logo-img-sm" />
          © 2026 Cortexa
        </div>
        <div className="flex items-center gap-6 text-xs" style={{ color: 'var(--text)' }}>
          <a href="#demo" className="hover:text-[#1C1C1E] transition-colors">How It Works</a>
          <a href="#manifesto" className="hover:text-[#1C1C1E] transition-colors">Manifesto</a>
          <a href="https://github.com/Arunjay4213/Cortexa" target="_blank" rel="noopener noreferrer"
            className="hover:text-[#1C1C1E] transition-colors flex items-center gap-1">
            GitHub <ExternalLink size={11} />
          </a>
        </div>
      </div>
    </footer>
  )
}
