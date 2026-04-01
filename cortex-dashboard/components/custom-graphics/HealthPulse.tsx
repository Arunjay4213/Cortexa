'use client'

import { motion } from 'framer-motion'

export default function HealthPulse() {
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
      {/* Heart rate monitor background */}
      <motion.path
        d="M10 60 L25 60 L35 40 L45 80 L55 30 L65 70 L75 50 L85 60 L110 60"
        stroke="url(#healthGradient)"
        strokeWidth="3"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0, opacity: 0 }}
        animate={{ pathLength: 1, opacity: 0.4 }}
        transition={{ duration: 1.5 }}
      />

      {/* Animated heartbeat line */}
      <motion.path
        d="M10 60 L25 60 L35 40 L45 80 L55 30 L65 70 L75 50 L85 60 L110 60"
        stroke="url(#healthGradientBright)"
        strokeWidth="4"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: [0, 1, 1, 0] }}
        transition={{
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut"
        }}
      />

      {/* Health indicator circles */}
      <motion.circle
        cx="60" cy="30" r="6"
        fill="#10b981"
        animate={{
          scale: [1, 1.3, 1],
          opacity: [1, 0.7, 1]
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity
        }}
      />

      {/* Glowing effect */}
      <motion.circle
        cx="60" cy="30" r="12"
        fill="none"
        stroke="#10b981"
        strokeWidth="2"
        opacity="0"
        animate={{
          scale: [1, 2],
          opacity: [0.6, 0]
        }}
        transition={{
          duration: 1.5,
          repeat: Infinity
        }}
      />

      <defs>
        <linearGradient id="healthGradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#10b981" stopOpacity="0.3" />
          <stop offset="50%" stopColor="#34d399" stopOpacity="0.6" />
          <stop offset="100%" stopColor="#10b981" stopOpacity="0.3" />
        </linearGradient>
        <linearGradient id="healthGradientBright" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#10b981" />
          <stop offset="50%" stopColor="#6ee7b7" />
          <stop offset="100%" stopColor="#10b981" />
        </linearGradient>
      </defs>
    </svg>
  )
}
