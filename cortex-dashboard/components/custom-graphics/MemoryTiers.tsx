'use client'

import { motion } from 'framer-motion'

export default function MemoryTiers() {
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Hot tier (top layer) */}
      <motion.g
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.1 }}
      >
        <rect x="20" y="20" width="80" height="20" rx="4" fill="url(#hotGradient)" />
        <motion.rect
          x="20" y="20" width="80" height="20" rx="4"
          fill="none"
          stroke="#ef4444"
          strokeWidth="2"
          opacity="0"
          animate={{
            opacity: [0, 0.6, 0]
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            repeatDelay: 0.5
          }}
        />
      </motion.g>

      {/* Warm tier (middle layer) */}
      <motion.g
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.3 }}
      >
        <rect x="25" y="50" width="70" height="18" rx="4" fill="url(#warmGradient)" />
      </motion.g>

      {/* Cold tier (bottom layer) */}
      <motion.g
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.6, delay: 0.5 }}
      >
        <rect x="30" y="78" width="60" height="18" rx="4" fill="url(#coldGradient)" />
      </motion.g>

      {/* Data flow particles */}
      <motion.circle
        cx="60" cy="30" r="3"
        fill="#fbbf24"
        animate={{
          cy: [30, 60, 87],
          opacity: [1, 0.5, 0]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          repeatDelay: 1
        }}
      />

      <defs>
        <linearGradient id="hotGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#ef4444" />
          <stop offset="100%" stopColor="#f97316" />
        </linearGradient>
        <linearGradient id="warmGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#f59e0b" />
          <stop offset="100%" stopColor="#fbbf24" />
        </linearGradient>
        <linearGradient id="coldGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#60a5fa" />
        </linearGradient>
      </defs>
    </svg>
  )
}
