'use client'

import { motion } from 'framer-motion'

export default function BrainNetwork() {
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Neural network nodes */}
      <motion.circle
        cx="60" cy="30" r="8"
        fill="url(#brainGradient1)"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{ duration: 0.6, delay: 0.1 }}
      />
      <motion.circle
        cx="30" cy="60" r="6"
        fill="url(#brainGradient2)"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{ duration: 0.6, delay: 0.2 }}
      />
      <motion.circle
        cx="90" cy="60" r="6"
        fill="url(#brainGradient2)"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{ duration: 0.6, delay: 0.3 }}
      />
      <motion.circle
        cx="45" cy="90" r="7"
        fill="url(#brainGradient3)"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{ duration: 0.6, delay: 0.4 }}
      />
      <motion.circle
        cx="75" cy="90" r="7"
        fill="url(#brainGradient3)"
        initial={{ scale: 0 }}
        animate={{ scale: [0, 1.2, 1] }}
        transition={{ duration: 0.6, delay: 0.5 }}
      />

      {/* Connecting lines with animation */}
      <motion.path
        d="M60 30 L30 60"
        stroke="url(#lineGradient)"
        strokeWidth="2"
        opacity="0.6"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, delay: 0.6 }}
      />
      <motion.path
        d="M60 30 L90 60"
        stroke="url(#lineGradient)"
        strokeWidth="2"
        opacity="0.6"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, delay: 0.7 }}
      />
      <motion.path
        d="M30 60 L45 90"
        stroke="url(#lineGradient)"
        strokeWidth="2"
        opacity="0.6"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, delay: 0.8 }}
      />
      <motion.path
        d="M90 60 L75 90"
        stroke="url(#lineGradient)"
        strokeWidth="2"
        opacity="0.6"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, delay: 0.9 }}
      />

      {/* Pulse effect */}
      <motion.circle
        cx="60" cy="30" r="12"
        fill="none"
        stroke="#3b82f6"
        strokeWidth="2"
        opacity="0"
        animate={{
          scale: [1, 1.5, 1],
          opacity: [0, 0.5, 0]
        }}
        transition={{
          duration: 2,
          repeat: Infinity,
          repeatDelay: 1
        }}
      />

      <defs>
        <linearGradient id="brainGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" />
          <stop offset="100%" stopColor="#8b5cf6" />
        </linearGradient>
        <linearGradient id="brainGradient2" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#6366f1" />
          <stop offset="100%" stopColor="#3b82f6" />
        </linearGradient>
        <linearGradient id="brainGradient3" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#8b5cf6" />
          <stop offset="100%" stopColor="#d946ef" />
        </linearGradient>
        <linearGradient id="lineGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.8" />
          <stop offset="100%" stopColor="#8b5cf6" stopOpacity="0.3" />
        </linearGradient>
      </defs>
    </svg>
  )
}
