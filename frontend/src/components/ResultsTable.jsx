import { useState, useMemo } from 'react';
import { ChevronUp, ChevronDown, Download } from 'lucide-react';
import { TIER_COLORS } from '../utils';

const TIER_BG = {
  LOW:      'bg-green-500/15 text-green-400',
  MEDIUM:   'bg-amber-500/15 text-amber-400',
  HIGH:     'bg-red-500/15 text-red-400',
  CRITICAL: 'bg-fuchsia-500/15 text-fuchsia-400',
};

const FILTER_BTNS = ['ALL', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'];

export default function ResultsTable({ predictions, transactions }) {
  const [filter, setFilter] = useState('ALL');
  const [sortField, setSortField] = useState('fraud_probability');
  const [sortDir, setSortDir] = useState('desc'); // 'asc' | 'desc'
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 25;

  // Merge transaction input data with prediction results
  const rows = useMemo(() => {
    return predictions.map((pred, i) => ({
      index: i + 1,
      amount: transactions?.[i]?.amount ?? pred.features_used?.amount ?? 0,
      nameOrig: transactions?.[i]?.nameOrig ?? '—',
      nameDest: transactions?.[i]?.nameDest ?? '—',
      type: transactions?.[i]?.type ?? '—',
      fraud_probability: pred.fraud_probability,
      risk_tier: pred.risk_tier,
      is_flagged: pred.is_flagged,
    }));
  }, [predictions, transactions]);

  // Filter
  const filtered = useMemo(() => {
    if (filter === 'ALL') return rows;
    return rows.filter((r) => r.risk_tier === filter);
  }, [rows, filter]);

  // Sort
  const sorted = useMemo(() => {
    return [...filtered].sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === 'number' && typeof bVal === 'number') {
        return sortDir === 'asc' ? aVal - bVal : bVal - aVal;
      }
      const aStr = String(aVal);
      const bStr = String(bVal);
      return sortDir === 'asc' ? aStr.localeCompare(bStr) : bStr.localeCompare(aStr);
    });
  }, [filtered, sortField, sortDir]);

  // Paginate
  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  const pageRows = sorted.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE);

  function handleSort(field) {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  }

  function SortIcon({ field }) {
    if (sortField !== field) return null;
    return sortDir === 'asc'
      ? <ChevronUp size={14} className="inline ml-1" />
      : <ChevronDown size={14} className="inline ml-1" />;
  }

  // CSV export
  function exportCsv() {
    const header = ['Row,Amount,Sender,Receiver,Type,Fraud Probability,Risk Tier,Flagged'];
    const csvRows = rows.map((r) =>
      [r.index, r.amount, r.nameOrig, r.nameDest, r.type, r.fraud_probability, r.risk_tier, r.is_flagged].join(',')
    );
    const blob = new Blob([header.concat(csvRows).join('\n')], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'fraud_scoring_results.csv';
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Filter buttons */}
        <div className="flex gap-2 flex-wrap">
          {FILTER_BTNS.map((tier) => {
            const count = tier === 'ALL' ? rows.length : rows.filter((r) => r.risk_tier === tier).length;
            const isActive = filter === tier;
            return (
              <button
                key={tier}
                onClick={() => { setFilter(tier); setPage(0); }}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 ${
                  isActive
                    ? 'bg-white/15 text-white shadow-[0_0_12px_rgba(139,92,246,0.3)]'
                    : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
                }`}
              >
                {tier} <span className="opacity-60">({count})</span>
              </button>
            );
          })}
        </div>

        {/* Export */}
        <button
          onClick={exportCsv}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white transition-all"
        >
          <Download size={14} /> Export CSV
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto results-table-container rounded-xl border border-white/5">
        <table className="results-table w-full text-sm">
          <thead>
            <tr>
              {[
                { key: 'index', label: '#' },
                { key: 'type', label: 'Type' },
                { key: 'amount', label: 'Amount' },
                { key: 'nameOrig', label: 'Sender' },
                { key: 'nameDest', label: 'Receiver' },
                { key: 'fraud_probability', label: 'Fraud Prob.' },
                { key: 'risk_tier', label: 'Risk Tier' },
                { key: 'is_flagged', label: 'Flagged' },
              ].map(({ key, label }) => (
                <th
                  key={key}
                  onClick={() => handleSort(key)}
                  className="cursor-pointer select-none px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-slate-400 hover:text-white transition-colors bg-black/30"
                >
                  {label}
                  <SortIcon field={key} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {pageRows.map((row) => (
              <tr key={row.index} className="results-row border-t border-white/5 hover:bg-white/5 transition-colors">
                <td className="px-4 py-2.5 text-slate-500 font-mono text-xs">{row.index}</td>
                <td className="px-4 py-2.5 font-medium">{row.type}</td>
                <td className="px-4 py-2.5 font-mono">${Number(row.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}</td>
                <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">{row.nameOrig}</td>
                <td className="px-4 py-2.5 text-slate-300 font-mono text-xs">{row.nameDest}</td>
                <td className="px-4 py-2.5 font-bold font-mono">{(row.fraud_probability * 100).toFixed(2)}%</td>
                <td className="px-4 py-2.5">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${TIER_BG[row.risk_tier] ?? ''}`}>
                    {row.risk_tier}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  {row.is_flagged
                    ? <span className="text-red-400 font-bold">🚨 YES</span>
                    : <span className="text-green-400">✅ NO</span>
                  }
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-slate-400">
          <span>
            Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, sorted.length)} of {sorted.length}
            {filter !== 'ALL' && ` (filtered from ${rows.length})`}
          </span>
          <div className="flex gap-2">
            <button
              disabled={page === 0}
              onClick={() => setPage((p) => p - 1)}
              className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              ← Prev
            </button>
            <button
              disabled={page >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
              className="px-3 py-1 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
