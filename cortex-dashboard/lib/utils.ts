import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatNumber(num: number, decimals: number = 2): string {
  return num.toFixed(decimals)
}

export function formatPercentage(num: number): string {
  return `${(num * 100).toFixed(1)}%`
}

export function formatCurrency(amount: number): string {
  if (Math.abs(amount) >= 1) {
    return `$${amount.toFixed(2)}`
  }
  if (Math.abs(amount) >= 0.01) {
    return `$${amount.toFixed(3)}`
  }
  return `$${amount.toFixed(4)}`
}

export function formatTimestamp(isoString: string): string {
  const now = new Date()
  const then = new Date(isoString)
  const diffMs = now.getTime() - then.getTime()

  if (diffMs < 0) return 'just now'

  const seconds = Math.floor(diffMs / 1000)
  if (seconds < 60) return `${seconds}s ago`

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`

  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`

  const months = Math.floor(days / 30)
  if (months < 12) return `${months}mo ago`

  const years = Math.floor(months / 12)
  return `${years}y ago`
}

export function formatMemoryId(id: string): string {
  const num = id.replace(/\D/g, '')
  return `#${num}`
}

export function classForHealth(score: number): string {
  if (score >= 0.8) return 'text-grafana-green'
  if (score >= 0.6) return 'text-grafana-yellow'
  return 'text-grafana-red'
}

export function classForROI(roi: number): string {
  if (roi > 10) return 'text-grafana-green'
  if (roi > 0) return 'text-grafana-yellow'
  return 'text-grafana-red'
}

/**
 * Returns Grafana-palette color classes for alert severity levels.
 */
export function classForSeverity(severity: 'critical' | 'warning' | 'info'): string {
  switch (severity) {
    case 'critical':
      return 'text-grafana-red'
    case 'warning':
      return 'text-grafana-yellow'
    case 'info':
      return 'text-grafana-blue'
  }
}

/**
 * Returns Grafana-palette background classes for alert severity levels.
 */
export function bgForSeverity(severity: 'critical' | 'warning' | 'info'): string {
  switch (severity) {
    case 'critical':
      return 'bg-[var(--stat-red-bg)]'
    case 'warning':
      return 'bg-[var(--stat-yellow-bg)]'
    case 'info':
      return 'bg-[var(--stat-blue-bg)]'
  }
}

export function truncateText(text: string, maxLength: number = 80): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength - 1) + '\u2026'
}
