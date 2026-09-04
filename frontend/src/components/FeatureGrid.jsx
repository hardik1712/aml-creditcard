/**
 * Staggered feature value grid shown after prediction.
 * @param {Object} features - key:value pairs from API response
 */
export default function FeatureGrid({ features = {} }) {
  const entries = Object.entries(features);
  if (!entries.length) return null;

  return (
    <details className="mt-6 border border-white/10 rounded-xl p-4">
      <summary className="cursor-pointer font-semibold text-slate-400 hover:text-white transition-colors select-none">
        🔬 Feature Values Used
      </summary>

      <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 gap-2 font-mono text-sm">
        {entries.map(([key, val], i) => (
          <div
            key={key}
            className="flex justify-between bg-black/20 hover:bg-white/10 hover:shadow-[0_0_15px_rgba(255,255,255,0.1)] transition-all duration-300 hover:scale-[1.05] hover:-translate-y-0.5 px-3 py-2 rounded-lg"
            style={{ animation: `fadeUp 0.35s ease ${i * 40}ms both` }}
          >
            <span className="text-slate-400 truncate mr-2">{key}</span>
            <span className="text-white font-semibold">{Number(val).toFixed(4)}</span>
          </div>
        ))}
      </div>
    </details>
  );
}
