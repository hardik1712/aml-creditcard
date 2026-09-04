import { useState } from 'react';
import { api } from '../api';
import Toast from '../components/Toast';
import RiskGauge from '../components/RiskGauge';
import FeatureGrid from '../components/FeatureGrid';
import AgentInvestigationModal from '../components/AgentInvestigationModal';
import { useAnimatedValue, TIER_COLORS } from '../utils';
import { Loader2, Send, Bot, Sparkles } from 'lucide-react';

const DEFAULTS = {
  step: 1, type: 'TRANSFER', amount: '9839.64',
  nameOrig: 'C1231006815', oldbalanceOrg: '170136.00', newbalanceOrig: '160296.36',
  nameDest: 'M1979787155', oldbalanceDest: '0.00', newbalanceDest: '0.00',
};

const TYPES = ['TRANSFER', 'CASH_OUT', 'CASH_IN', 'PAYMENT', 'DEBIT'];

function Field({ label, children }) {
  return (
    <div className="input-wrapper group">
      {children}
      <label className="floating-label">{label}</label>
    </div>
  );
}

const inputCls = "floating-input";

export default function Scorer() {
  const [form, setForm]       = useState(DEFAULTS);
  const [loading, setLoading] = useState(false);
  const [result, setResult]   = useState(null);
  const [toast, setToast]     = useState(null);
  const [investigation, setInvestigation] = useState(null);
  const [investigating, setInvestigating] = useState(false);

  const animatedProb = useAnimatedValue(
    result ? result.fraud_probability * 100 : null,
    { decimals: 4, suffix: '%' }
  );

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    try {
      const payload = {
        step:           parseInt(form.step),
        type:           form.type,
        amount:         parseFloat(form.amount),
        nameOrig:       form.nameOrig,
        oldbalanceOrg:  parseFloat(form.oldbalanceOrg),
        newbalanceOrig: parseFloat(form.newbalanceOrig),
        nameDest:       form.nameDest,
        oldbalanceDest: parseFloat(form.oldbalanceDest),
        newbalanceDest: parseFloat(form.newbalanceDest),
      };
      const data = await api.predict(payload);
      setResult(data);
      setToast({ message: 'Transaction scored successfully!', type: 'success' });
    } catch (err) {
      setToast({ message: err.message || 'Prediction failed', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  async function handleLaunchInvestigation() {
    setInvestigating(true);
    try {
      const payload = {
        step:           parseInt(form.step),
        type:           form.type,
        amount:         parseFloat(form.amount),
        nameOrig:       form.nameOrig,
        oldbalanceOrg:  parseFloat(form.oldbalanceOrg),
        newbalanceOrig: parseFloat(form.newbalanceOrig),
        nameDest:       form.nameDest,
        oldbalanceDest: parseFloat(form.oldbalanceDest),
        newbalanceDest: parseFloat(form.newbalanceDest),
      };
      const data = await api.investigate(payload);
      setInvestigation(data);
    } catch (err) {
      setToast({ message: err.message || 'Investigation failed', type: 'error' });
    } finally {
      setInvestigating(false);
    }
  }

  const tierColor = result ? TIER_COLORS[result.risk_tier] ?? TIER_COLORS.LOW : '';

  return (
    <section className="animate-fade-up space-y-6">
      {/* Toast */}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onDismiss={() => setToast(null)}
        />
      )}

      {/* Form card */}
      <div className="glass p-8">
        <h3 className="text-xl font-bold mb-6 flex items-center gap-2">
          📝 Transaction Details
        </h3>
        <form onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-7">
            <Field label="Step (hour)">
              <input type="number" min={1} value={form.step} onChange={set('step')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="Transaction Type">
              <select value={form.type} onChange={set('type')} className={`${inputCls} has-value`} required>
                {TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </Field>

            <Field label="Amount ($)">
              <input type="number" step="0.01" min={0} value={form.amount} onChange={set('amount')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="Originator Account">
              <input type="text" value={form.nameOrig} onChange={set('nameOrig')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="Old Balance (Orig)">
              <input type="number" step="0.01" min={0} value={form.oldbalanceOrg} onChange={set('oldbalanceOrg')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="New Balance (Orig)">
              <input type="number" step="0.01" min={0} value={form.newbalanceOrig} onChange={set('newbalanceOrig')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="Destination Account">
              <input type="text" value={form.nameDest} onChange={set('nameDest')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="Old Balance (Dest)">
              <input type="number" step="0.01" min={0} value={form.oldbalanceDest} onChange={set('oldbalanceDest')} className={inputCls} required placeholder=" " />
            </Field>

            <Field label="New Balance (Dest)">
              <input type="number" step="0.01" min={0} value={form.newbalanceDest} onChange={set('newbalanceDest')} className={inputCls} required placeholder=" " />
            </Field>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="gradient-btn w-full text-white font-bold py-3.5 rounded-xl flex items-center justify-center gap-2 text-base"
          >
            {loading ? (
              <><Loader2 size={18} className="animate-spin" /> Scoring…</>
            ) : (
              <><Send size={18} /> Score Transaction</>
            )}
          </button>
        </form>
      </div>

      {/* Result card */}
      {result && (
        <div className="glass p-8 animate-fade-up space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h3 className="text-xl font-bold">🎯 Prediction Result</h3>
            <button
              onClick={handleLaunchInvestigation}
              disabled={investigating}
              className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs flex items-center gap-2 transition shadow-lg shadow-violet-600/30 disabled:opacity-50"
            >
              {investigating ? (
                <><Loader2 size={14} className="animate-spin" /> Investigating…</>
              ) : (
                <><Bot size={14} /> Launch Agent Investigation & SAR</>
              )}
            </button>
          </div>

          {/* KPI row */}
          <div className="grid grid-cols-3 gap-4 mb-2">
            {/* Probability */}
            <div className="bg-black/20 rounded-xl p-5 text-center animate-fade-up" style={{ animationDelay: '100ms' }}>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Fraud Probability</div>
              <div className="text-3xl font-extrabold gradient-text">{animatedProb}</div>
            </div>

            {/* Risk Tier */}
            <div className="bg-black/20 rounded-xl p-5 text-center flex flex-col items-center justify-center gap-2 animate-fade-up" style={{ animationDelay: '200ms' }}>
              <div className="text-xs text-slate-400 uppercase tracking-wider">Risk Tier</div>
              <span className={`border-2 ${tierColor} px-4 py-1 rounded-full text-lg font-extrabold ${result.risk_tier === 'CRITICAL' ? 'animate-pulse-slow' : ''}`}>
                {result.risk_tier}
              </span>
            </div>

            {/* Flagged */}
            <div className="bg-black/20 rounded-xl p-5 text-center animate-fade-up" style={{ animationDelay: '300ms' }}>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Flagged</div>
              <div className={`text-3xl font-extrabold ${result.is_flagged ? 'text-red-400' : 'text-green-400'}`}>
                {result.is_flagged ? '🚨 YES' : '✅ NO'}
              </div>
            </div>
          </div>

          {/* Gauge */}
          <RiskGauge probability={result.fraud_probability} tier={result.risk_tier} />

          {/* Feature list */}
          <FeatureGrid features={result.features_used} />
        </div>
      )}

      {/* Agent Investigation Modal */}
      {investigation && (
        <AgentInvestigationModal
          investigation={investigation}
          onClose={() => setInvestigation(null)}
        />
      )}
    </section>
  );
}

