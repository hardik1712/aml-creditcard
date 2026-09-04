import { useState, useRef, useCallback } from 'react';
import { api } from '../api';
import Toast from '../components/Toast';
import ResultsTable from '../components/ResultsTable';
import KpiCard from '../components/KpiCard';
import { Loader2, Upload, FileSpreadsheet, CheckCircle, AlertTriangle, ArrowRight, RotateCcw } from 'lucide-react';

const STEPS = ['Upload File', 'Map Columns', 'Results'];

const FIELD_LABELS = {
  step:           { label: 'Time Step (hour)',      required: false },
  type:           { label: 'Transaction Type',      required: true },
  amount:         { label: 'Amount ($)',             required: true },
  nameOrig:       { label: 'Sender Account',        required: true },
  oldbalanceOrg:  { label: 'Sender Balance Before', required: false },
  newbalanceOrig: { label: 'Sender Balance After',  required: false },
  nameDest:       { label: 'Receiver Account',      required: true },
  oldbalanceDest: { label: 'Receiver Balance Before', required: false },
  newbalanceDest: { label: 'Receiver Balance After',  required: false },
};

function StepIndicator({ current }) {
  return (
    <div className="flex items-center justify-center gap-0 mb-10">
      {STEPS.map((label, i) => {
        const done = i < current;
        const active = i === current;
        return (
          <div key={label} className="flex items-center">
            {/* Circle */}
            <div className="flex flex-col items-center">
              <div
                className={`w-9 h-9 rounded-full flex items-center justify-center text-sm font-bold transition-all duration-500 ${
                  done
                    ? 'bg-green-500 text-white shadow-[0_0_14px_rgba(34,197,94,0.4)]'
                    : active
                      ? 'bg-gradient-to-br from-indigo-500 to-fuchsia-500 text-white shadow-[0_0_18px_rgba(139,92,246,0.5)]'
                      : 'bg-white/10 text-slate-500'
                }`}
              >
                {done ? <CheckCircle size={18} /> : i + 1}
              </div>
              <span className={`text-xs mt-2 font-medium ${active ? 'text-white' : 'text-slate-500'}`}>
                {label}
              </span>
            </div>
            {/* Connector */}
            {i < STEPS.length - 1 && (
              <div className={`w-16 h-0.5 mx-2 mb-6 transition-all duration-500 ${done ? 'bg-green-500' : 'bg-white/10'}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function FileUpload() {
  const [step, setStep]           = useState(0);
  const [file, setFile]           = useState(null);
  const [preview, setPreview]     = useState(null);
  const [mapping, setMapping]     = useState({});
  const [result, setResult]       = useState(null);
  const [loading, setLoading]     = useState(false);
  const [toast, setToast]         = useState(null);
  const [dragOver, setDragOver]   = useState(false);
  const inputRef = useRef(null);

  // --------------- Step 0: File selection ---------------

  const handleFile = useCallback(async (f) => {
    if (!f) return;
    const validExts = ['csv', 'xlsx', 'xls'];
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (!validExts.includes(ext)) {
      setToast({ message: 'Please upload a .csv, .xlsx, or .xls file.', type: 'error' });
      return;
    }
    setFile(f);
    setLoading(true);
    try {
      const data = await api.uploadPreview(f);
      setPreview(data);
      setMapping(data.auto_mapping);
      setStep(1);
      setToast({ message: `File parsed: ${data.total_rows.toLocaleString()} rows detected`, type: 'success' });
    } catch (err) {
      setToast({ message: err.message || 'Failed to parse file', type: 'error' });
    } finally {
      setLoading(false);
    }
  }, []);

  function onDrop(e) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    handleFile(f);
  }

  function onBrowse(e) {
    handleFile(e.target.files[0]);
  }

  // --------------- Step 1: Column mapping ---------------

  function setMappingField(field, value) {
    setMapping((m) => ({ ...m, [field]: value || null }));
  }

  async function handleScore() {
    if (!file) return;
    setLoading(true);
    try {
      const data = await api.uploadAndScore(file, mapping);
      setResult(data);
      setStep(2);
      setToast({
        message: `Scored ${data.summary.total_scored.toLocaleString()} transactions — ${data.summary.flagged_count} flagged`,
        type: data.summary.flagged_count > 0 ? 'warning' : 'success',
      });
    } catch (err) {
      setToast({ message: err.message || 'Scoring failed', type: 'error' });
    } finally {
      setLoading(false);
    }
  }

  // --------------- Reset ---------------

  function reset() {
    setStep(0);
    setFile(null);
    setPreview(null);
    setMapping({});
    setResult(null);
    if (inputRef.current) inputRef.current.value = '';
  }

  // --------------- Check if required mappings are set ---------------

  const requiredFieldsMapped = ['type', 'amount', 'nameOrig', 'nameDest'].every(
    (f) => mapping[f] != null && mapping[f] !== ''
  );

  return (
    <section className="animate-fade-up space-y-6">
      {toast && <Toast message={toast.message} type={toast.type} onDismiss={() => setToast(null)} />}

      <StepIndicator current={step} />

      {/* ───────────────── Step 0: Upload ───────────────── */}
      {step === 0 && (
        <div className="glass p-8 animate-fade-up">
          <h3 className="text-xl font-bold mb-2 flex items-center gap-2">
            <Upload size={20} className="text-violet-400" /> Upload Transaction File
          </h3>
          <p className="text-slate-400 text-sm mb-6">
            Upload a CSV or Excel file containing transaction data. The system will auto-detect
            column mappings and score every row for fraud risk.
          </p>

          {/* Drop zone */}
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            className={`drop-zone cursor-pointer flex flex-col items-center justify-center py-16 rounded-2xl border-2 border-dashed transition-all duration-300 ${
              dragOver
                ? 'border-violet-500 bg-violet-500/10 shadow-[0_0_30px_rgba(139,92,246,0.2)]'
                : 'border-white/10 bg-black/20 hover:border-white/20 hover:bg-black/30'
            }`}
          >
            {loading ? (
              <Loader2 size={40} className="text-violet-400 animate-spin mb-3" />
            ) : (
              <FileSpreadsheet size={40} className="text-violet-400 mb-3" />
            )}
            <span className="text-white font-semibold mb-1">
              {loading ? 'Parsing file…' : 'Drag & drop your file here'}
            </span>
            <span className="text-slate-500 text-sm">or click to browse • CSV, XLSX, XLS • Max 10MB</span>
            <input
              ref={inputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={onBrowse}
              className="hidden"
            />
          </div>
        </div>
      )}

      {/* ───────────────── Step 1: Column Mapping ───────────────── */}
      {step === 1 && preview && (
        <div className="space-y-6 animate-fade-up">
          {/* File info */}
          <div className="glass p-6 flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <FileSpreadsheet size={18} className="text-violet-400" />
                <span className="font-bold text-white">{preview.filename}</span>
              </div>
              <span className="text-slate-400 text-sm">
                {preview.total_rows.toLocaleString()} rows • {preview.columns.length} columns
              </span>
            </div>
            <button onClick={reset} className="text-slate-400 hover:text-white text-sm flex items-center gap-1 transition-colors">
              <RotateCcw size={14} /> Change file
            </button>
          </div>

          {/* Preview table */}
          <div className="glass p-6">
            <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4">Data Preview (first 5 rows)</h4>
            <div className="overflow-x-auto rounded-xl border border-white/5">
              <table className="results-table w-full text-xs">
                <thead>
                  <tr>
                    {preview.columns.map((col) => (
                      <th key={col} className="px-3 py-2 text-left text-slate-400 font-semibold bg-black/30 whitespace-nowrap">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.preview_rows.map((row, i) => (
                    <tr key={i} className="border-t border-white/5">
                      {preview.columns.map((col) => (
                        <td key={col} className="px-3 py-2 whitespace-nowrap text-slate-300">
                          {row[col] != null ? String(row[col]) : <span className="text-slate-600">null</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Column mapping editor */}
          <div className="glass p-6">
            <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-1">Column Mapping</h4>
            <p className="text-slate-500 text-xs mb-5">
              Review the auto-detected mappings below. Adjust any that look incorrect.
              Fields marked with <span className="text-fuchsia-400 font-bold">★</span> are required.
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(FIELD_LABELS).map(([field, { label, required }]) => {
                const current = mapping[field];
                const isMatched = current != null;
                return (
                  <div key={field} className="input-wrapper group">
                    <select
                      value={current ?? ''}
                      onChange={(e) => setMappingField(field, e.target.value)}
                      className={`floating-input has-value text-sm ${
                        isMatched ? '' : required ? 'border-red-500/50' : 'border-amber-500/30'
                      }`}
                    >
                      <option value="">— Not Mapped —</option>
                      {preview.columns.map((col) => (
                        <option key={col} value={col}>{col}</option>
                      ))}
                    </select>
                    <label className="floating-label">
                      {required && <span className="text-fuchsia-400 mr-1">★</span>}
                      {label}
                    </label>
                  </div>
                );
              })}
            </div>

            {!requiredFieldsMapped && (
              <div className="mt-4 flex items-center gap-2 text-amber-400 text-sm">
                <AlertTriangle size={16} />
                <span>All required fields (★) must be mapped before scoring.</span>
              </div>
            )}
          </div>

          {/* Score button */}
          <button
            onClick={handleScore}
            disabled={loading || !requiredFieldsMapped}
            className="gradient-btn w-full text-white font-bold py-3.5 rounded-xl flex items-center justify-center gap-2 text-base"
          >
            {loading ? (
              <><Loader2 size={18} className="animate-spin" /> Scoring {preview.total_rows.toLocaleString()} transactions…</>
            ) : (
              <><ArrowRight size={18} /> Score All Transactions</>
            )}
          </button>
        </div>
      )}

      {/* ───────────────── Step 2: Results ───────────────── */}
      {step === 2 && result && (
        <div className="space-y-6 animate-fade-up">
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-6">
            <KpiCard label="Total Scored"    value={result.summary.total_scored}     icon="📋"  color="border-violet-500" />
            <KpiCard label="Flagged"         value={result.summary.flagged_count}    icon="🚨"  color="border-red-500" />
            <KpiCard label="Avg Probability" value={result.summary.avg_probability * 100} suffix="%" decimals={2} icon="📊" color="border-amber-500" />
            <KpiCard label="Max Probability" value={result.summary.max_probability * 100} suffix="%" decimals={2} icon="🎯" color="border-fuchsia-500" />
          </div>

          {/* Tier distribution bar */}
          <div className="glass p-6">
            <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4">Risk Tier Distribution</h4>
            <div className="flex rounded-xl overflow-hidden h-8">
              {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((tier) => {
                const count = result.summary.tier_distribution[tier] ?? 0;
                const pct = result.summary.total_scored > 0
                  ? (count / result.summary.total_scored) * 100
                  : 0;
                if (pct === 0) return null;
                const colors = {
                  LOW:      'bg-green-500',
                  MEDIUM:   'bg-amber-500',
                  HIGH:     'bg-red-500',
                  CRITICAL: 'bg-fuchsia-500',
                };
                return (
                  <div
                    key={tier}
                    className={`${colors[tier]} flex items-center justify-center text-xs font-bold text-white/90 transition-all`}
                    style={{ width: `${Math.max(pct, 3)}%` }}
                    title={`${tier}: ${count} (${pct.toFixed(1)}%)`}
                  >
                    {pct >= 8 && `${tier} ${count}`}
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 mt-3 text-xs text-slate-400">
              {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((tier) => {
                const count = result.summary.tier_distribution[tier] ?? 0;
                const dotColors = {
                  LOW: 'bg-green-500', MEDIUM: 'bg-amber-500', HIGH: 'bg-red-500', CRITICAL: 'bg-fuchsia-500',
                };
                return (
                  <span key={tier} className="flex items-center gap-1.5">
                    <span className={`w-2 h-2 rounded-full ${dotColors[tier]}`} />
                    {tier}: {count}
                  </span>
                );
              })}
            </div>
          </div>

          {/* Warnings */}
          {result.warnings?.length > 0 && (
            <div className="glass p-5 border-amber-500/30">
              <h4 className="text-sm font-bold text-amber-400 mb-2 flex items-center gap-2">
                <AlertTriangle size={16} /> Parsing Warnings
              </h4>
              <ul className="text-xs text-slate-400 space-y-1 list-disc list-inside">
                {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
              </ul>
            </div>
          )}

          {/* Results table */}
          <div className="glass p-6">
            <h4 className="text-sm font-bold text-slate-300 uppercase tracking-wider mb-4">Transaction Scores</h4>
            <ResultsTable predictions={result.predictions} />
          </div>

          {/* Reset button */}
          <button
            onClick={reset}
            className="flex items-center gap-2 text-slate-400 hover:text-white text-sm transition-colors mx-auto"
          >
            <RotateCcw size={14} /> Upload another file
          </button>
        </div>
      )}
    </section>
  );
}
