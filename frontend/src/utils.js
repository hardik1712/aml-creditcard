import { useEffect, useRef, useState } from 'react';

/**
 * Smoothly animates a numeric value from `from` to `to` over `duration` ms.
 * Returns the current animated value as a string.
 */
export function useAnimatedValue(to, { duration = 900, decimals = 2, suffix = '' } = {}) {
  const [display, setDisplay] = useState('—');
  const rafRef = useRef(null);

  useEffect(() => {
    if (to == null || isNaN(to)) return;
    const start = performance.now();
    const from = 0;

    const step = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 4); // easeOutQuart
      const current = from + eased * (to - from);
      setDisplay(current.toFixed(decimals) + suffix);
      if (progress < 1) rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [to, duration, decimals, suffix]);

  return display;
}

/** Clamp a number between min and max */
export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/** Map risk_tier string to a colour class */
export const TIER_COLORS = {
  LOW:      'text-green-400 border-green-500',
  MEDIUM:   'text-amber-400 border-amber-500',
  HIGH:     'text-red-400   border-red-500',
  CRITICAL: 'text-fuchsia-400 border-fuchsia-500',
};

export const TIER_GAUGE_COLORS = {
  LOW:      '#22c55e',
  MEDIUM:   '#f59e0b',
  HIGH:     '#ef4444',
  CRITICAL: '#d946ef',
};
