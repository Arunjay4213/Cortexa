'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { LucideIcon } from 'lucide-react';

/**
 * HOLOGRAPHIC ETCHED ICON SYSTEM
 *
 * Features:
 * - Micro-glass container (40x40px, 1px border at 10% white opacity)
 * - Drop shadow glow (0 0 5px accent color)
 * - 50% opacity fill for "etched glass" effect
 * - "Ignition" state when metric spikes (blue → amber/red with pulse)
 * - Crisp edges (shape-rendering: geometricPrecision)
 * - No blurry edges - razor-sharp SVG paths
 */

type IconState = 'idle' | 'warning' | 'critical' | 'success';

interface HolographicIconProps {
  /** Lucide icon component */
  icon: LucideIcon;

  /** Current state determines color and animation */
  state?: IconState;

  /** Size in pixels (default: 40) */
  size?: number;

  /** Custom accent color (overrides state color) */
  accentColor?: string;

  /** Enable pulsing animation */
  pulse?: boolean;

  /** Click handler */
  onClick?: () => void;
}

export function HolographicIcon({
  icon: Icon,
  state = 'idle',
  size = 40,
  accentColor,
  pulse = false,
  onClick,
}: HolographicIconProps) {
  // State-based colors
  const stateColors = {
    idle: '#64D2FF',      // Cool blue (default)
    warning: '#FF9F0A',   // Amber (heating up)
    critical: '#FF3B30',  // Red (ignited)
    success: '#34C759',   // Green (optimal)
  };

  const glowColor = accentColor || stateColors[state];
  const iconSize = size * 0.5; // Icon is 50% of container

  // Pulse animation (for critical/warning states)
  const shouldPulse = pulse || state === 'critical' || state === 'warning';

  return (
    <motion.div
      className="holographic-icon-container"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        position: 'relative',
        cursor: onClick ? 'pointer' : 'default',
      }}
      onClick={onClick}
      // Hover magnetics (1.01 scale)
      whileHover={{
        scale: 1.01,
        transition: { duration: 0.2, ease: 'easeOut' },
      }}
      // Click feedback (0.98 scale)
      whileTap={onClick ? {
        scale: 0.98,
        transition: { duration: 0.05 },
      } : undefined}
    >
      {/* Micro-glass container */}
      <motion.div
        className="micro-glass-frame"
        style={{
          width: '100%',
          height: '100%',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '8px',
          background: 'rgba(10, 10, 10, 0.4)',
          backdropFilter: 'blur(10px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
        }}
        // Pulse glow animation
        animate={shouldPulse ? {
          boxShadow: [
            `0 0 5px ${glowColor}`,
            `0 0 15px ${glowColor}, 0 0 25px ${glowColor}80`,
            `0 0 5px ${glowColor}`,
          ],
        } : {
          boxShadow: `0 0 5px ${glowColor}`,
        }}
        transition={{
          duration: 2,
          repeat: shouldPulse ? Infinity : 0,
          ease: 'easeInOut',
        }}
      >
        {/* Scanline effect (barely visible) */}
        <motion.div
          className="icon-scanline"
          style={{
            position: 'absolute',
            top: 0,
            left: '-100%',
            width: '100%',
            height: '100%',
            background: `linear-gradient(90deg, transparent 0%, ${glowColor}10 50%, transparent 100%)`,
            pointerEvents: 'none',
          }}
          animate={{
            left: ['100%', '-100%'],
          }}
          transition={{
            duration: 10,
            repeat: Infinity,
            ease: 'linear',
          }}
        />

        {/* Icon with etched glass effect */}
        <motion.div
          style={{
            position: 'relative',
            zIndex: 1,
          }}
          // Color transition on state change
          animate={{
            filter: `drop-shadow(0 0 5px ${glowColor})`,
          }}
          transition={{ duration: 0.3 }}
        >
          <Icon
            size={iconSize}
            strokeWidth={1.5}
            style={{
              color: glowColor,
              opacity: 0.5, // 50% opacity for etched effect
              shapeRendering: 'geometricPrecision', // Crisp edges
            }}
          />
        </motion.div>

        {/* Inner glow overlay */}
        <div
          className="inner-glow"
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: '60%',
            height: '60%',
            background: `radial-gradient(circle, ${glowColor}20 0%, transparent 70%)`,
            pointerEvents: 'none',
            opacity: state === 'critical' ? 0.8 : 0.3,
            transition: 'opacity 0.3s',
          }}
        />
      </motion.div>

      {/* Click flash overlay */}
      {onClick && (
        <motion.div
          className="click-flash"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(255, 255, 255, 0.3)',
            borderRadius: '8px',
            pointerEvents: 'none',
            opacity: 0,
          }}
          // Flash on click (handled by parent whileTap)
        />
      )}
    </motion.div>
  );
}

/**
 * HELPER: Icon Grid Container
 * For displaying multiple holographic icons in a grid
 */
interface IconGridProps {
  children: React.ReactNode;
  columns?: number;
  gap?: number;
}

export function IconGrid({ children, columns = 4, gap = 8 }: IconGridProps) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap: `${gap}px`,
      }}
    >
      {children}
    </div>
  );
}

/**
 * HELPER: Animated Icon State
 * Automatically transitions icon state based on metric value
 */
export function useIconState(
  value: number,
  thresholds: { critical: number; warning: number; success: number }
): IconState {
  if (value >= thresholds.critical) return 'critical';
  if (value >= thresholds.warning) return 'warning';
  if (value <= thresholds.success) return 'success';
  return 'idle';
}
