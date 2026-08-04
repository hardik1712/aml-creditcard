import { useAnimatedValue } from '../utils';

/**
 * KPI Card with animated counter.
 * @param {string}  label
 * @param {number|string}  value - if numeric, animates; if string, shows directly
 * @param {string}  suffix - appended after numeric value (e.g. '%')
 * @param {number}  decimals
 * @param {string}  icon  - emoji or element
 * @param {string}  color - Tailwind color class for accent border
 */
export default function KpiCard({ label, value, suffix = '', decimals = 0, icon, color = 'border-violet-500' }) {
  const isNumeric = typeof value === 'number';
  const animated  = useAnimatedValue(isNumeric ? value : null, { decimals, suffix });

  return (
    <div className={`glass p-6 flex flex-col gap-2 border-t-2 ${color} hover:-translate-y-1 transition-transform duration-200`}>
      <div className="flex items-center justify-between">
        <span className="text-xs uppercase tracking-widest text-slate-400 font-semibold">{label}</span>
        {icon && <span className="text-xl">{icon}</span>}
      </div>
      <div className="text-3xl font-extrabold text-white mt-1">
        {isNumeric ? animated : value}
      </div>
    </div>
  );
}
