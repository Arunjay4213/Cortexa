'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion } from 'framer-motion';
import { LayoutDashboard, GitBranch, Activity, Cpu } from 'lucide-react';

export function Navigation() {
  const pathname = usePathname();

  const links = [
    { href: '/', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/memory-flow', label: 'Memory Flow', icon: GitBranch },
    { href: '/cockpit', label: 'Cockpit', icon: Activity },
    { href: '/engine', label: 'Engine', icon: Cpu },
  ];

  return (
    <nav className="fixed top-4 left-1/2 -translate-x-1/2 z-50 bg-black/90 backdrop-blur-md border border-white/20 rounded-lg px-2 py-2 flex gap-1">
      {links.map((link) => {
        const isActive = pathname === link.href;
        const Icon = link.icon;

        return (
          <Link key={link.href} href={link.href}>
            <motion.div
              className={`px-4 py-2 rounded-md text-sm font-bold flex items-center gap-2 transition-colors ${
                isActive
                  ? 'bg-[#00D9FF] text-black'
                  : 'text-white/60 hover:text-white hover:bg-white/10'
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              <Icon size={16} />
              {link.label}
            </motion.div>
          </Link>
        );
      })}
    </nav>
  );
}
