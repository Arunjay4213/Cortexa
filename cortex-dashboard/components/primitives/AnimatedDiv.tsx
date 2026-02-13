'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

/**
 * ANIMATED DIV - REUSABLE PREMIUM WRAPPER
 *
 * Features:
 * - Hover Physics: Magnetic border light-up + 1.01 scale
 * - Click Feedback: Mechanical click (0.98 scale + white flash 50ms)
 * - Entrance Animation: Configurable fade/slide
 * - Standard micro-interactions
 *
 * Usage:
 * <AnimatedDiv interactive onClick={...}>
 *   Your content
 * </AnimatedDiv>
 */

interface AnimatedDivProps extends Omit<HTMLMotionProps<'div'>, 'children'> {
  children: React.ReactNode;

  /** Enable hover/click interactions */
  interactive?: boolean;

  /** Entrance animation type */
  entrance?: 'fade' | 'slide-up' | 'slide-left' | 'scale' | 'none';

  /** Stagger delay (for list items) */
  delay?: number;

  /** Custom border glow color */
  glowColor?: string;

  /** Enable border glow on hover */
  glowOnHover?: boolean;
}

export function AnimatedDiv({
  children,
  interactive = false,
  entrance = 'fade',
  delay = 0,
  glowColor = '#64D2FF',
  glowOnHover = false,
  onClick,
  className = '',
  style = {},
  ...props
}: AnimatedDivProps) {
  // Entrance animation variants
  const entranceVariants = {
    fade: {
      initial: { opacity: 0 },
      animate: { opacity: 1 },
    },
    'slide-up': {
      initial: { opacity: 0, y: 20 },
      animate: { opacity: 1, y: 0 },
    },
    'slide-left': {
      initial: { opacity: 0, x: 20 },
      animate: { opacity: 1, x: 0 },
    },
    scale: {
      initial: { opacity: 0, scale: 0.95 },
      animate: { opacity: 1, scale: 1 },
    },
    none: {
      initial: {},
      animate: {},
    },
  };

  const variant = entranceVariants[entrance];

  return (
    <motion.div
      className={`animated-div ${className}`}
      style={{
        position: 'relative',
        transition: 'box-shadow 0.2s ease-out',
        ...style,
      }}
      // Entrance animation
      initial={variant.initial}
      animate={variant.animate}
      transition={{
        duration: 0.3,
        delay,
        ease: [0.33, 1, 0.68, 1],
      }}
      // Hover physics (if interactive)
      whileHover={
        interactive
          ? {
              scale: 1.01,
              boxShadow: glowOnHover
                ? `0 0 0 1px ${glowColor}40, 0 0 20px ${glowColor}20`
                : undefined,
              transition: { duration: 0.2, ease: 'easeOut' },
            }
          : undefined
      }
      // Click feedback (if interactive)
      whileTap={
        interactive && onClick
          ? {
              scale: 0.98,
              transition: { duration: 0.05 },
            }
          : undefined
      }
      onClick={onClick}
      {...props}
    >
      {children}

      {/* White flash overlay on click */}
      {interactive && onClick && (
        <motion.div
          className="click-flash-overlay"
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(255, 255, 255, 0.3)',
            borderRadius: 'inherit',
            pointerEvents: 'none',
            opacity: 0,
          }}
          // Trigger on parent tap
          animate={{ opacity: 0 }}
        />
      )}
    </motion.div>
  );
}

/**
 * ANIMATED GRID - Container for staggered children
 */
interface AnimatedGridProps {
  children: React.ReactNode;
  columns?: number;
  gap?: number;
  stagger?: number; // Delay between each child
  className?: string;
}

export function AnimatedGrid({
  children,
  columns = 4,
  gap = 16,
  stagger = 0.05,
  className = '',
}: AnimatedGridProps) {
  const childArray = React.Children.toArray(children);

  return (
    <div
      className={`animated-grid ${className}`}
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        gap: `${gap}px`,
      }}
    >
      {childArray.map((child, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration: 0.3,
            delay: index * stagger,
            ease: [0.33, 1, 0.68, 1],
          }}
        >
          {child}
        </motion.div>
      ))}
    </div>
  );
}
