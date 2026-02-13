'use client'

import { motion } from 'framer-motion'
import { LucideIcon, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useMemo } from 'react'

interface MetricCardProps {
  label: string
  value: string | number
  unit?: string
  trend?: number // percentage change
  sparkline?: number[]
  status?: 'good' | 'warning' | 'critical' | 'neutral'
  icon?: LucideIcon
  onClick?: () => void
  loading?: boolean
}

export default function MetricCard({
  label,
  value,
  unit,
  trend,
  sparkline,
  status = 'neutral',
  icon: Icon,
  onClick,
  loading = false
}: MetricCardProps) {
  const statusColors = {
    good: 'border-success/30 bg-success/5',
    warning: 'border-warning/30 bg-warning/5',
    critical: 'border-critical/30 bg-critical/5',
    neutral: 'border-border bg-background'
  }

  const statusGlows = {
    good: 'shadow-[0_0_20px_rgba(16,185,129,0.15)]',
    warning: 'shadow-[0_0_20px_rgba(245,158,11,0.15)]',
    critical: 'shadow-[0_0_20px_rgba(239,68,68,0.15)]',
    neutral: ''
  }

  const trendColor = useMemo(() => {
    if (!trend) return 'text-foreground/50'
    if (trend > 0) return 'text-success'
    if (trend < 0) return 'text-critical'
    return 'text-foreground/50'
  }, [trend])

  const TrendIcon = useMemo(() => {
    if (!trend) return Minus
    return trend > 0 ? TrendingUp : TrendingDown
  }, [trend])

  const sparklinePoints = useMemo(() => {
    if (!sparkline || sparkline.length === 0) return ''
    const max = Math.max(...sparkline)
    const min = Math.min(...sparkline)
    const range = max - min || 1
    const width = 60
    const height = 20

    return sparkline
      .map((val, i) => {
        const x = (i / (sparkline.length - 1)) * width
        const y = height - ((val - min) / range) * height
        return `${x},${y}`
      })
      .join(' ')
  }, [sparkline])

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: onClick ? 1.02 : 1 }}
      whileTap={{ scale: onClick ? 0.98 : 1 }}
      onClick={onClick}
      className={`
        relative overflow-hidden rounded-lg border p-4
        ${statusColors[status]}
        ${statusGlows[status]}
        ${onClick ? 'cursor-pointer transition-all hover:border-foreground/20' : ''}
      `}
    >
      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 bg-background/50 backdrop-blur-sm flex items-center justify-center">
          <div className="w-5 h-5 border-2 border-foreground/20 border-t-foreground rounded-full animate-spin" />
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          {Icon && (
            <div className={`
              p-1.5 rounded-md
              ${status === 'good' ? 'bg-success/10 text-success' : ''}
              ${status === 'warning' ? 'bg-warning/10 text-warning' : ''}
              ${status === 'critical' ? 'bg-critical/10 text-critical' : ''}
              ${status === 'neutral' ? 'bg-foreground/5 text-foreground/60' : ''}
            `}>
              <Icon className="w-4 h-4" />
            </div>
          )}
          <span className="text-xs font-medium text-foreground/60 uppercase tracking-wide">
            {label}
          </span>
        </div>

        {trend !== undefined && (
          <div className={`flex items-center gap-1 text-xs font-mono ${trendColor}`}>
            <TrendIcon className="w-3 h-3" />
            <span>{Math.abs(trend).toFixed(1)}%</span>
          </div>
        )}
      </div>

      {/* Value */}
      <div className="flex items-baseline gap-1 mb-2">
        <span className="text-3xl font-bold font-mono tabular-nums">
          {loading ? '—' : value}
        </span>
        {unit && (
          <span className="text-sm text-foreground/50 font-medium">
            {unit}
          </span>
        )}
      </div>

      {/* Sparkline */}
      {sparkline && sparkline.length > 0 && (
        <div className="h-5 mt-3">
          <svg
            width="100%"
            height="20"
            viewBox="0 0 60 20"
            preserveAspectRatio="none"
            className="opacity-60"
          >
            <polyline
              points={sparklinePoints}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
              className={
                status === 'good' ? 'text-success' :
                status === 'warning' ? 'text-warning' :
                status === 'critical' ? 'text-critical' :
                'text-foreground/40'
              }
            />
          </svg>
        </div>
      )}

      {/* Status indicator dot */}
      <div className="absolute top-2 right-2">
        <div className={`
          w-2 h-2 rounded-full
          ${status === 'good' ? 'bg-success animate-pulse-glow' : ''}
          ${status === 'warning' ? 'bg-warning animate-pulse-glow' : ''}
          ${status === 'critical' ? 'bg-critical animate-pulse-glow' : ''}
          ${status === 'neutral' ? 'bg-foreground/20' : ''}
        `} />
      </div>
    </motion.div>
  )
}
