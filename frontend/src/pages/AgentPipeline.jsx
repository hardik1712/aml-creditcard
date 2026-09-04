import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  Zap, 
  Bot, 
  ShieldCheck, 
  ShieldAlert, 
  AlertTriangle, 
  Lock, 
  FileText, 
  Activity, 
  ArrowRight,
  Filter,
  Search,
  ExternalLink,
  Sparkles
} from 'lucide-react';
import { api } from '../api';
import AgentInvestigationModal from '../components/AgentInvestigationModal';

const ACTION_CONFIG = {
  AUTO_APPROVE: {
    label: 'Auto-Approved',
    badge: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    icon: ShieldCheck,
  },
  MONITOR: {
    label: 'Under Surveillance',
    badge: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    icon: AlertTriangle,
  },
  MANUAL_REVIEW: {
    label: 'Queued Review',
    badge: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    icon: AlertTriangle,
  },
  BLOCK_TRANSACTION: {
    label: 'Blocked',
    badge: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
    icon: ShieldAlert,
  },
  FREEZE_ACCOUNT: {
    label: 'Account Frozen',
    badge: 'bg-red-600/20 border-red-500/40 text-red-400 font-bold animate-pulse',
    icon: Lock,
  },
};

export default function AgentPipeline() {
  const [isRunning, setIsRunning] = useState(false);
  const [speedTps, setSpeedTps] = useState(1.5);
  const [stats, setStats] = useState({
    total_ingested: 0,
    total_approved: 0,
    total_flagged: 0,
    total_sars_generated: 0,
  });
  const [events, setEvents] = useState([]);
  const [filterTier, setFilterTier] = useState('ALL'); // ALL | SAR | FLAGGED | APPROVED
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedInvestigation, setSelectedInvestigation] = useState(null);
  const [isInjecting, setIsInjecting] = useState(false);

  // Polling stream status
  useEffect(() => {
    let interval = null;

    const pollStatus = async () => {
      try {
        const data = await api.getStreamStatus();
        setIsRunning(data.is_running);
        setStats({
          total_ingested: data.total_ingested,
          total_approved: data.total_approved,
          total_flagged: data.total_flagged,
          total_sars_generated: data.total_sars_generated,
        });
        if (data.recent_events && data.recent_events.length > 0) {
          setEvents(data.recent_events);
        }
      } catch (err) {
        console.error('Failed to poll stream status:', err);
      }
    };

    pollStatus();
    interval = setInterval(pollStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleToggleStream = async () => {
    try {
      if (isRunning) {
        await api.stopStream();
        setIsRunning(false);
      } else {
        await api.startStream(speedTps);
        setIsRunning(true);
      }
    } catch (err) {
      console.error('Stream toggle error:', err);
    }
  };

  const handleReset = async () => {
    try {
      await api.resetStream();
      setStats({
        total_ingested: 0,
        total_approved: 0,
        total_flagged: 0,
        total_sars_generated: 0,
      });
      setEvents([]);
    } catch (err) {
      console.error('Reset error:', err);
    }
  };

  const handleInjectBatch = async () => {
    setIsInjecting(true);
    try {
      // Generate burst transactions
      const burst = [];
      for (let i = 0; i < 10; i++) {
        const isFraud = i % 3 === 0;
        burst.push({
          step: 20 + i,
          type: isFraud ? 'TRANSFER' : 'PAYMENT',
          amount: isFraud ? 195000.0 : 120.50,
          nameOrig: `C${Math.floor(1000000000 + Math.random() * 9000000000)}`,
          oldbalanceOrg: isFraud ? 195000.0 : 2500.0,
          newbalanceOrig: isFraud ? 0.0 : 2379.50,
          nameDest: `M${Math.floor(1000000000 + Math.random() * 9000000000)}`,
          oldbalanceDest: 0.0,
          newbalanceDest: isFraud ? 0.0 : 120.50,
        });
      }
      await api.processPipelineBatch(burst);
      const data = await api.getStreamStatus();
      setEvents(data.recent_events);
    } catch (err) {
      console.error('Burst injection failed:', err);
    } finally {
      setIsInjecting(false);
    }
  };

  const handleOpenInvestigation = async (event) => {
    try {
      const tx = {
        step: event.step,
        type: event.type,
        amount: event.amount,
        nameOrig: event.nameOrig,
        oldbalanceOrg: event.oldbalanceOrg,
        newbalanceOrig: event.newbalanceOrig,
        nameDest: event.nameDest,
        oldbalanceDest: event.oldbalanceDest,
        newbalanceDest: event.newbalanceDest,
      };
      const res = await api.investigate(tx);
      setSelectedInvestigation(res);
    } catch (err) {
      console.error('Failed to run investigation:', err);
    }
  };

  const filteredEvents = events.filter((ev) => {
    if (filterTier === 'SAR' && !ev.sar_generated) return false;
    if (filterTier === 'FLAGGED' && ev.agent_action === 'AUTO_APPROVE') return false;
    if (filterTier === 'APPROVED' && ev.agent_action !== 'AUTO_APPROVE') return false;
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      return (
        ev.tx_id.toLowerCase().includes(term) ||
        ev.nameOrig.toLowerCase().includes(term) ||
        ev.nameDest.toLowerCase().includes(term) ||
        ev.type.toLowerCase().includes(term)
      );
    }
    return true;
  });

  return (
    <div className="space-y-8">
      {/* Top Banner & Control Deck */}
      <div className="glass p-6 rounded-2xl border border-white/10 space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30 flex items-center gap-1">
                <Sparkles size={12} />
                AUTONOMOUS PIPELINE
              </span>
              {isRunning && (
                <span className="flex items-center gap-1 text-xs text-emerald-400 font-medium animate-pulse">
                  <span className="w-2 h-2 rounded-full bg-emerald-400" />
                  Live Ingestion Active
                </span>
              )}
            </div>
            <h2 className="text-2xl font-bold text-white">Automated Ingestion & Triage Hub</h2>
            <p className="text-slate-400 text-sm">
              Continuous core-banking transaction stream interception, automated feature extraction, and agentic containment.
            </p>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-3 flex-wrap">
            <button
              onClick={handleToggleStream}
              className={`px-5 py-2.5 rounded-xl font-bold text-sm flex items-center gap-2 transition shadow-lg ${
                isRunning
                  ? 'bg-rose-600 hover:bg-rose-500 text-white shadow-rose-600/30'
                  : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-600/30'
              }`}
            >
              {isRunning ? <Pause size={16} /> : <Play size={16} />}
              {isRunning ? 'Pause Ingestion' : 'Start Auto-Feed'}
            </button>

            <button
              onClick={handleInjectBatch}
              disabled={isInjecting}
              className="px-4 py-2.5 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/30 font-semibold text-sm flex items-center gap-1.5 transition disabled:opacity-50"
            >
              <Zap size={15} />
              {isInjecting ? 'Processing…' : 'Burst Batch (10 TX)'}
            </button>

            <button
              onClick={handleReset}
              className="p-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white transition"
              title="Reset counters"
            >
              <RotateCcw size={16} />
            </button>
          </div>
        </div>

        {/* Pipeline Stage Architecture Flow */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2">
          {[
            { step: '1. Ingestion Stream', desc: 'Auto-detects schemas & parses feeds', active: isRunning },
            { step: '2. Feature Pipeline', desc: 'Ledger discrepancy & velocity extraction', active: isRunning },
            { step: '3. LightGBM Inference', desc: 'Gradient boosted fraud scoring', active: isRunning },
            { step: '4. Agent Triage & SAR', desc: 'Auto-actions & FinCEN filing', active: isRunning },
          ].map((st, i) => (
            <div 
              key={i}
              className={`p-3.5 rounded-xl border transition-all duration-300 ${
                st.active 
                  ? 'bg-violet-950/20 border-violet-500/30 text-white' 
                  : 'bg-slate-900/30 border-white/5 text-slate-500'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">{st.step}</span>
                {st.active && <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-ping" />}
              </div>
              <p className="text-[11px] text-slate-400 leading-tight">{st.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* KPI Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="glass p-5 rounded-2xl border border-white/10 space-y-1">
          <div className="text-xs text-slate-400 font-medium">Total Ingested</div>
          <div className="text-3xl font-extrabold text-white">{stats.total_ingested.toLocaleString()}</div>
          <div className="text-[11px] text-slate-500">Continuous background stream</div>
        </div>

        <div className="glass p-5 rounded-2xl border border-white/10 space-y-1">
          <div className="text-xs text-slate-400 font-medium">Auto-Approved</div>
          <div className="text-3xl font-extrabold text-emerald-400">{stats.total_approved.toLocaleString()}</div>
          <div className="text-[11px] text-emerald-500/80 font-medium">
            {stats.total_ingested > 0 ? ((stats.total_approved / stats.total_ingested) * 100).toFixed(1) : 100}% frictionless
          </div>
        </div>

        <div className="glass p-5 rounded-2xl border border-white/10 space-y-1">
          <div className="text-xs text-slate-400 font-medium">Flagged & Blocked</div>
          <div className="text-3xl font-extrabold text-amber-400">{stats.total_flagged.toLocaleString()}</div>
          <div className="text-[11px] text-amber-500/80 font-medium">Under active containment</div>
        </div>

        <div className="glass p-5 rounded-2xl border border-white/10 space-y-1">
          <div className="text-xs text-slate-400 font-medium">SARs Auto-Generated</div>
          <div className="text-3xl font-extrabold text-violet-400">{stats.total_sars_generated.toLocaleString()}</div>
          <div className="text-[11px] text-violet-400/80 font-medium">FinCEN compliant narratives</div>
        </div>
      </div>

      {/* Live Transaction Feed Table */}
      <div className="glass rounded-2xl border border-white/10 overflow-hidden space-y-4 p-6">
        {/* Table Filters */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Activity className="text-violet-400" size={18} />
            <h3 className="text-lg font-bold text-white">Live Stream Interception Feed</h3>
            <span className="text-xs text-slate-400">({filteredEvents.length} events)</span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {/* Search */}
            <div className="relative">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="text"
                placeholder="Filter by TX, Account ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="bg-slate-900 border border-white/10 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-violet-500 w-48"
              />
            </div>

            {/* Filter Pills */}
            <div className="flex bg-slate-900 rounded-xl p-1 border border-white/10 text-xs">
              {[
                { id: 'ALL', label: 'All' },
                { id: 'SAR', label: 'SAR Filed' },
                { id: 'FLAGGED', label: 'Flagged' },
                { id: 'APPROVED', label: 'Approved' },
              ].map((pill) => (
                <button
                  key={pill.id}
                  onClick={() => setFilterTier(pill.id)}
                  className={`px-3 py-1 rounded-lg font-medium transition ${
                    filterTier === pill.id
                      ? 'bg-violet-600 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {pill.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-slate-300">
            <thead className="bg-slate-900/60 text-slate-400 border-b border-white/10 uppercase tracking-wider text-[10px]">
              <tr>
                <th className="py-3 px-4 font-semibold">Tx ID & Time</th>
                <th className="py-3 px-4 font-semibold">Channel</th>
                <th className="py-3 px-4 font-semibold">Originator ➔ Beneficiary</th>
                <th className="py-3 px-4 font-semibold text-right">Amount</th>
                <th className="py-3 px-4 font-semibold">Risk Score</th>
                <th className="py-3 px-4 font-semibold">Agent Action</th>
                <th className="py-3 px-4 font-semibold text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-12 text-center text-slate-500">
                    {isRunning ? 'Waiting for incoming stream transactions…' : 'Stream is paused. Click "Start Auto-Feed" or "Burst Batch" to ingest transactions.'}
                  </td>
                </tr>
              ) : (
                filteredEvents.map((ev) => {
                  const actionCfg = ACTION_CONFIG[ev.agent_action] || ACTION_CONFIG.MANUAL_REVIEW;
                  const ActionIcon = actionCfg.icon;

                  return (
                    <tr 
                      key={ev.tx_id}
                      className="hover:bg-white/5 transition duration-150 group"
                    >
                      <td className="py-3 px-4 font-mono">
                        <div className="text-white font-bold">{ev.tx_id}</div>
                        <div className="text-[10px] text-slate-500">{ev.timestamp} · Step {ev.step}</div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-white/10 text-slate-200">
                          {ev.type}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="font-mono text-xs flex items-center gap-1.5">
                          <span className="text-slate-300">{ev.nameOrig}</span>
                          <ArrowRight size={12} className="text-slate-600" />
                          <span className="text-slate-300">{ev.nameDest}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold text-white">
                        ${ev.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${
                          ev.risk_tier === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                          ev.risk_tier === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border-orange-500/30' :
                          ev.risk_tier === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' :
                          'bg-emerald-500/20 text-emerald-400 border-emerald-500/30'
                        }`}>
                          {ev.risk_tier} ({(ev.fraud_probability * 100).toFixed(1)}%)
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-semibold border flex items-center gap-1 ${actionCfg.badge}`}>
                            <ActionIcon size={12} />
                            {actionCfg.label}
                          </span>
                          {ev.sar_generated && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-violet-600/30 text-violet-300 border border-violet-500/40 flex items-center gap-1">
                              <FileText size={10} />
                              SAR
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => handleOpenInvestigation(ev)}
                          className="px-3 py-1 rounded-lg bg-white/10 hover:bg-violet-600 text-slate-200 hover:text-white font-medium text-xs transition flex items-center gap-1 ml-auto"
                        >
                          <Bot size={12} />
                          Investigate
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Investigation & SAR Modal */}
      {selectedInvestigation && (
        <AgentInvestigationModal
          investigation={selectedInvestigation}
          onClose={() => setSelectedInvestigation(null)}
        />
      )}
    </div>
  );
}
