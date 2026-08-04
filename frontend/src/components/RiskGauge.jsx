import { useEffect, useRef } from 'react';
import { TIER_GAUGE_COLORS } from '../utils';

/**
 * Animated horizontal gauge bar.
 * @param {number} probability  - 0..1
 * @param {string} tier         - LOW | MEDIUM | HIGH | CRITICAL
 */
export default function RiskGauge({ probability = 0, tier = 'LOW' }) {
  const fillRef = useRef(null);
  const color   = TIER_GAUGE_COLORS[tier] ?? TIER_GAUGE_COLORS.LOW;
  const pct     = Math.min(Math.max(probability * 100, 0), 100);

  useEffect(() => {
    if (!fillRef.current) return;
    // Animate via WAAPI so it works even if CSS transition isn't applied yet
    fillRef.current.animate(
      [{ width: '0%' }, { width: `${pct}%` }],
      { duration: 1000, easing: 'cubic-bezier(0.4,0,0.2,1)', fill: 'forwards' }
    );
  }, [pct]);

  return (
    <div className="mt-4 mb-6">
      {/* Labels */}
      <div className="flex justify-between text-xs text-slate-500 mb-2">
        <span>0%</span>
        <span className="font-semibold text-slate-300">{pct.toFixed(2)}% fraud probability</span>
        <span>100%</span>
      </div>

      {/* Track */}
      <div className="relative h-3 bg-white/5 rounded-full overflow-hidden border border-white/5">
        {/* Gradient background track */}
        <div className="absolute inset-0 opacity-20"
          style={{ background: 'linear-gradient(to right, #22c55e, #f59e0b, #ef4444, #d946ef)' }} />
        {/* Fill */}
        <div
          ref={fillRef}
          className="absolute top-0 left-0 h-full rounded-full"
          style={{ width: '0%', background: color }}
        />
      </div>

      {/* Tier labels */}
      <div className="flex justify-between text-xs text-slate-600 mt-1">
        <span>LOW</span>
        <span>MEDIUM</span>
        <span>HIGH</span>
        <span>CRITICAL</span>
      </div>
    </div>
  );
}
