'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, useSpring, useTransform } from 'framer-motion';

/**
 * ANIMATED NUMBER - ODOMETER/SLOT MACHINE EFFECT
 *
 * Features:
 * - Numbers "scroll" into place like an odometer
 * - Smooth spring physics
 * - Configurable decimal places
 * - Optional suffix (%, ms, $, etc.)
 * - Crisp monospace rendering
 */

interface AnimatedNumberProps {
  /** Target value to animate to */
  value: number;

  /** Number of decimal places */
  decimals?: number;

  /** Prefix (e.g., "$") */
  prefix?: string;

  /** Suffix (e.g., "ms", "%") */
  suffix?: string;

  /** Animation duration in seconds */
  duration?: number;

  /** Font size */
  fontSize?: string;

  /** Custom className */
  className?: string;
}

export function AnimatedNumber({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
  duration = 0.5,
  fontSize = '64px',
  className = '',
}: AnimatedNumberProps) {
  const [displayValue, setDisplayValue] = useState(value);

  // Spring animation for smooth transition
  const spring = useSpring(value, {
    stiffness: 100,
    damping: 30,
    mass: 1,
  });

  // Update spring when value changes
  useEffect(() => {
    spring.set(value);
  }, [value, spring]);

  // Transform spring to formatted string
  useEffect(() => {
    const unsubscribe = spring.on('change', (latest) => {
      setDisplayValue(latest);
    });
    return unsubscribe;
  }, [spring]);

  // Format number with decimals
  const formatted = displayValue.toFixed(decimals);

  return (
    <div
      className={`animated-number font-mono ${className}`}
      style={{
        fontSize,
        fontWeight: 700,
        lineHeight: 1,
        fontVariantNumeric: 'tabular-nums',
        letterSpacing: '-0.02em',
      }}
    >
      {prefix}
      <motion.span
        key={formatted} // Re-mount on change for slot effect
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{
          duration: duration,
          ease: [0.33, 1, 0.68, 1], // Custom ease-out
        }}
        style={{ display: 'inline-block' }}
      >
        {formatted}
      </motion.span>
      {suffix}
    </div>
  );
}

/**
 * DIGIT ROLLER - Individual Digit Animation
 * For more granular control (rolling each digit separately)
 */
interface DigitRollerProps {
  digit: number; // 0-9
  fontSize?: string;
}

export function DigitRoller({ digit, fontSize = '64px' }: DigitRollerProps) {
  const digits = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9];
  const digitHeight = parseInt(fontSize) * 1.2; // Line height

  return (
    <div
      style={{
        height: `${digitHeight}px`,
        overflow: 'hidden',
        display: 'inline-block',
        position: 'relative',
        width: `${parseInt(fontSize) * 0.6}px`,
      }}
    >
      <motion.div
        animate={{
          y: -digit * digitHeight,
        }}
        transition={{
          type: 'spring',
          stiffness: 300,
          damping: 30,
        }}
      >
        {digits.map((d) => (
          <div
            key={d}
            style={{
              height: `${digitHeight}px`,
              fontSize,
              fontWeight: 700,
              fontFamily: 'var(--font-mono)',
              lineHeight: `${digitHeight}px`,
              textAlign: 'center',
            }}
          >
            {d}
          </div>
        ))}
      </motion.div>
    </div>
  );
}

/**
 * MULTI-DIGIT ROLLER
 * Rolls each digit independently for maximum effect
 */
interface MultiDigitRollerProps {
  value: number;
  decimals?: number;
  fontSize?: string;
}

export function MultiDigitRoller({
  value,
  decimals = 0,
  fontSize = '64px',
}: MultiDigitRollerProps) {
  const formatted = value.toFixed(decimals);
  const chars = formatted.split('');

  return (
    <div style={{ display: 'inline-flex', gap: '2px' }}>
      {chars.map((char, index) => {
        if (char === '.') {
          return (
            <span
              key={`dot-${index}`}
              style={{
                fontSize,
                fontWeight: 700,
                lineHeight: 1,
              }}
            >
              .
            </span>
          );
        }

        const digit = parseInt(char);
        if (isNaN(digit)) return char;

        return <DigitRoller key={`digit-${index}`} digit={digit} fontSize={fontSize} />;
      })}
    </div>
  );
}
