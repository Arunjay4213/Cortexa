'use client';

import React from 'react';
import { motion } from 'framer-motion';

/**
 * GLANCEABLE METRIC CARD
 *
 * Design Philosophy:
 * - 80% number, 20% context (Bloomberg Terminal density)
 * - Pre-attentive processing: Color = Severity
 * - Monospace for perfect alignment
 * - Fixed height for Z-pattern scanning consistency
 *
 * WCAG AAA Compliant:
 * - All colors: 7:1+ contrast on black
 * - Redundant encoding (color + icon + border thickness)
 * - Keyboard accessible
 */

type Severity = 'critical' | 'high' | 'medium' | 'low' | 'success' | 'info';
type TrendDirection = 'up' | 'down' | 'neutral';

interface MetricCardProps {
  /** Metric label (uppercase, compact) */
  label: string;

  /** Primary value (dominates 80% of card) */
  value: string | number;

  /** Unit text (e.g., "ms", "$", "%") */
  unit?: string;

  /** Severity determines color, border, glow */
  severity?: Severity;

  /** Trend indicator */
  trend?: {
    direction: TrendDirection;
    delta: string;
    percentage?: string;
  };

  /** Tooltip info icon content */
  tooltip?: string;

  /** Sparkline data (optional, shows on hover) */
  sparkline?: number[];

  /** Click handler */
  onClick?: () => void;

  /** ARIA label for accessibility */
  ariaLabel?: string;

  /** Loading state */
  loading?: boolean;
}

export function MetricCard({
  label,
  value,
  unit,
  severity = 'info',
  trend,
  tooltip,
  sparkline,
  onClick,
  ariaLabel,
  loading = false,
}: MetricCardProps) {
  // Determine CSS class based on severity
  const severityClass = `metric-card--${severity}`;

  // Trend arrow icon
  const getTrendIcon = (direction: TrendDirection) => {
    switch (direction) {
      case 'up':
        return '▲';
      case 'down':
        return '▼';
      case 'neutral':
        return '━';
    }
  };

  // Trend CSS class
  const getTrendClass = (direction: TrendDirection) => {
    return `metric-card__trend--${direction}`;
  };

  // Loading skeleton
  if (loading) {
    return (
      <div className={`metric-card ${severityClass}`}>
        <div className="metric-card__header">
          <div className="skeleton" style={{ width: '80px', height: '12px' }} />
        </div>
        <div className="metric-card__value">
          <div className="skeleton" style={{ width: '120px', height: '64px' }} />
        </div>
        {trend && (
          <div className="skeleton" style={{ width: '100px', height: '12px' }} />
        )}
      </div>
    );
  }

  return (
    <motion.div
      className={`metric-card ${severityClass} ${onClick ? 'cursor-pointer' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : 'article'}
      aria-label={ariaLabel || `${label}: ${value}${unit || ''}`}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (onClick && (e.key === 'Enter' || e.key === ' ')) {
          e.preventDefault();
          onClick();
        }
      }}
      // Entrance animation (fade-in-up)
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.33, 1, 0.68, 1] }}
      // Hover animation (subtle scale)
      whileHover={{ scale: 1.02 }}
      whileTap={onClick ? { scale: 0.98 } : undefined}
    >
      {/* Header: Label + Tooltip */}
      <div className="metric-card__header">
        <span className="metric-label">{label}</span>
        {tooltip && (
          <button
            className="btn--ghost btn--sm"
            aria-label="More information"
            title={tooltip}
            style={{ padding: '4px', minWidth: 'unset' }}
          >
            <InfoIcon />
          </button>
        )}
      </div>

      {/* Value Container (80% of vertical space) */}
      <div className="metric-card__value">
        <div className="metric-value">
          {value}
        </div>
        {unit && (
          <div className="metric-card__unit">
            {unit}
          </div>
        )}
      </div>

      {/* Trend Indicator (Compact, bottom) */}
      {trend && (
        <div className={`metric-card__trend ${getTrendClass(trend.direction)}`}>
          <span>{getTrendIcon(trend.direction)}</span>
          <span>{trend.delta}</span>
          {trend.percentage && (
            <span className="metric-meta">({trend.percentage})</span>
          )}
        </div>
      )}

      {/* Sparkline (Optional, hover-reveal) */}
      {sparkline && sparkline.length > 0 && (
        <div className="metric-card__sparkline">
          <Sparkline data={sparkline} color={getSeverityColor(severity)} />
        </div>
      )}
    </motion.div>
  );
}

/**
 * INFO ICON (Minimalist)
 */
function InfoIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      style={{ opacity: 0.6 }}
    >
      <circle cx="8" cy="8" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path
        d="M8 7V11M8 5V5.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

/**
 * SPARKLINE (Mini Line Chart)
 * Simple SVG path for hover-reveal trend
 */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  const width = 80;
  const height = 24;
  const padding = 2;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1; // Avoid division by zero

  // Create SVG path
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * (width - 2 * padding) + padding;
    const y = height - padding - ((value - min) / range) * (height - 2 * padding);
    return `${x},${y}`;
  });

  const pathData = `M ${points.join(' L ')}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <path
        d={pathData}
        stroke={color}
        strokeWidth="2"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

/**
 * Get severity color for sparkline
 */
function getSeverityColor(severity: Severity): string {
  const colors = {
    critical: '#FF3B30',
    high: '#FF9500',
    medium: '#FFD60A',
    low: '#64D2FF',
    success: '#34C759',
    info: '#98989D',
  };
  return colors[severity];
}

/**
 * HELPER: Calculate severity from metric value and thresholds
 */
export function calculateSeverity(
  value: number,
  thresholds: { critical: number; high: number; medium: number; low: number },
  higherIsBetter = false
): Severity {
  if (higherIsBetter) {
    // For metrics like accuracy where higher is better
    if (value >= thresholds.low) return 'low'; // Good
    if (value >= thresholds.medium) return 'medium';
    if (value >= thresholds.high) return 'high';
    return 'critical';
  } else {
    // For metrics like latency where lower is better
    if (value <= thresholds.low) return 'low'; // Good
    if (value <= thresholds.medium) return 'medium';
    if (value <= thresholds.high) return 'high';
    return 'critical';
  }
}

/**
 * HELPER: Format metric value for display
 */
export function formatMetricValue(value: number, format: 'number' | 'percentage' | 'currency' | 'duration'): string {
  switch (format) {
    case 'number':
      return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
    case 'percentage':
      return `${(value * 100).toFixed(2)}%`;
    case 'currency':
      return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    case 'duration':
      // Convert ms to appropriate unit
      if (value < 1000) return `${value.toFixed(1)} ms`;
      if (value < 60000) return `${(value / 1000).toFixed(2)} s`;
      return `${(value / 60000).toFixed(2)} m`;
  }
}
