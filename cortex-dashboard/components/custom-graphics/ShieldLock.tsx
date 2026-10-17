'use client'

import { motion } from 'framer-motion'

export default function ShieldLock() {
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Shield outer glow */}
      <motion.path
        d="M60 10 L90 25 L90 55 C90 75 75 95 60 110 C45 95 30 75 30 55 L30 25 L60 10 Z"
        fill="url(#shieldGlow)"
        opacity="0.3"
        animate={{
          scale: [1, 1.05, 1],
          opacity: [0.3, 0.5, 0.3]
        }}
        transition={{
          duration: 3,
          repeat: Infinity
        }}
      />

      {/* Main shield */}
      <motion.path
        d="M60 15 L85 27 L85 52 C85 70 72 88 60 102 C48 88 35 70 35 52 L35 27 L60 15 Z"
        fill="url(#shieldGradient)"
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.8, delay: 0.2 }}
      />

      {/* Lock icon */}
      <motion.g
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ duration: 0.4, delay: 0.6 }}
      >
        {/* Lock body */}
        <rect x="50" y="55" width="20" height="18" rx="2" fill="#fff" opacity="0.9" />

        {/* Lock shackle */}
        <path
          d="M54 55 L54 48 C54 44.6863 56.6863 42 60 42 C63.3137 42 66 44.6863 66 48 L66 55"
          stroke="#fff"
          strokeWidth="3"
          strokeLinecap="round"
          fill="none"
          opacity="0.9"
        />

        {/* Keyhole */}
        <circle cx="60" cy="62" r="2.5" fill="#8b5cf6" />
        <rect x="58.5" y="62" width="3" height="6" rx="1" fill="#8b5cf6" />
      </motion.g>

      {/* Scanning lines */}
      <motion.line
        x1="35" y1="40" x2="85" y2="40"
        stroke="#a78bfa"
        strokeWidth="2"
        opacity="0"
        animate={{
          y1: [30, 100],
          y2: [30, 100],
          opacity: [0, 0.6, 0]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          repeatDelay: 1
        }}
      />

      <defs>
        <linearGradient id="shieldGradient" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="50%" stopColor="#7c3aed" />
          <stop offset="100%" stopColor="#6d28d9" />
        </linearGradient>
        <radialGradient id="shieldGlow">
          <stop offset="0%" stopColor="#8b5cf6" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0" />
        </radialGradient>
      </defs>
    </svg>
  )
}
