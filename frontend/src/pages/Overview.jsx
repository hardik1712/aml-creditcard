import { useCallback, useEffect, useState } from 'react';
import { api } from '../api';
import KpiCard from '../components/KpiCard';
import { Brain, Layers, ShieldCheck, TrendingUp } from 'lucide-react';

const STATIC_KPIS = [
  { label: 'Total Transactions', value: '6.3M',  icon: '📋', color: 'border-violet-500' },
  { label: 'Fraud Cases',        value: '8,213', icon: '🚨', color: 'border-red-500'    },
  { label: 'Fraud Rate',         value: '0.13%', icon: '📉', color: 'border-amber-500'  },
];

export default function Overview() {
  const [metrics, setMetrics]   = useState(null);
  const [modelInfo, setModelInfo] = useState(null);
  const [loading, setLoading]   = useState(true);

  const load = useCallback(async () => {
    try {
      const [m, i] = await Promise.all([api.modelMetrics(), api.modelInfo()]);
      setMetrics(m);
      setModelInfo(i);
    } catch (e) {
      console.error('Failed to load model info', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <section className="animate-fade-up space-y-8">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {STATIC_KPIS.map((k) => (
          <KpiCard key={k.label} {...k} />
        ))}
        <KpiCard
          label="Model Precision"
          value={metrics ? metrics.precision * 100 : null}
          suffix="%"
          decimals={2}
          icon="🎯"
          color="border-green-500"
        />
      </div>

      {/* Model Info Card */}
      <div className="glass p-6">
        <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
          <Brain size={20} className="text-violet-400" />
          Model Information
        </h3>

        {loading ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="bg-white/5 rounded-xl h-20 animate-pulse" />
            ))}
          </div>
        ) : modelInfo ? (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {[
              { label: 'Model Type',       value: modelInfo.model_type,     icon: <Layers size={16} className="text-violet-400" /> },
              { label: 'Features',         value: modelInfo.n_features,     icon: <TrendingUp size={16} className="text-sky-400" /> },
              { label: 'Low Risk Cutoff',  value: `< ${(modelInfo.risk_thresholds.LOW * 100).toFixed(0)}%`, icon: <ShieldCheck size={16} className="text-green-400" /> },
              { label: 'High Risk Cutoff', value: `> ${(modelInfo.risk_thresholds.HIGH * 100).toFixed(0)}%`, icon: <ShieldCheck size={16} className="text-red-400" /> },
            ].map(({ label, value, icon }) => (
              <div key={label} className="bg-black/20 rounded-xl p-4">
                <div className="flex items-center gap-2 text-slate-400 text-xs mb-2">{icon} {label}</div>
                <div className="text-white font-bold text-lg">{value}</div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Could not load model information.</p>
        )}

        {/* Metrics details */}
        {metrics && (
          <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              ['Accuracy',  metrics.accuracy],
              ['Recall',    metrics.recall],
              ['F1 Score',  metrics.f1],
              ['ROC-AUC',   metrics.roc_auc],
            ].map(([name, val]) => (
              <div key={name} className="bg-black/20 rounded-xl p-3 text-center">
                <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">{name}</div>
                <div className="gradient-text text-xl font-extrabold">
                  {val != null ? (val * 100).toFixed(2) + '%' : 'N/A'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
