import React, { useState } from 'react';
import { 
  ShieldAlert, 
  ShieldCheck, 
  AlertTriangle, 
  Lock, 
  FileText, 
  Copy, 
  Check, 
  Download, 
  X, 
  Bot, 
  Sparkles, 
  Activity, 
  ArrowRight,
  Send
} from 'lucide-react';
import { api } from '../api';

const ACTION_CONFIG = {
  AUTO_APPROVE: {
    label: 'Auto-Approved',
    bg: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400',
    icon: ShieldCheck,
  },
  MONITOR: {
    label: 'Under Surveillance',
    bg: 'bg-amber-500/10 border-amber-500/30 text-amber-400',
    icon: AlertTriangle,
  },
  MANUAL_REVIEW: {
    label: 'Queued for Review',
    bg: 'bg-orange-500/10 border-orange-500/30 text-orange-400',
    icon: AlertTriangle,
  },
  BLOCK_TRANSACTION: {
    label: 'Transaction Blocked',
    bg: 'bg-rose-500/10 border-rose-500/30 text-rose-400',
    icon: ShieldAlert,
  },
  FREEZE_ACCOUNT: {
    label: 'Account Frozen',
    bg: 'bg-red-600/20 border-red-500/40 text-red-400 animate-pulse',
    icon: Lock,
  },
};

const SEVERITY_BADGE = {
  CRITICAL: 'bg-red-500/20 text-red-300 border-red-500/30',
  HIGH:     'bg-orange-500/20 text-orange-300 border-orange-500/30',
  MEDIUM:   'bg-amber-500/20 text-amber-300 border-amber-500/30',
  LOW:      'bg-slate-500/20 text-slate-300 border-slate-500/30',
};

export default function AgentInvestigationModal({ investigation, onClose }) {
  const [activeTab, setActiveTab] = useState('summary'); // summary | sar | copilot
  const [copied, setCopied] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputQuery, setInputQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  if (!investigation) return null;

  const {
    transaction: tx,
    fraud_probability: proba,
    risk_tier: tier,
    recommended_action: action,
    risk_factors: factors,
    agent_reasoning: reasoning,
    sar_report: sar,
  } = investigation;

  const actionCfg = ACTION_CONFIG[action] || ACTION_CONFIG.MANUAL_REVIEW;
  const ActionIcon = actionCfg.icon;

  const handleCopySAR = () => {
    if (!sar?.narrative_summary) return;
    navigator.clipboard.writeText(sar.narrative_summary);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadSAR = () => {
    if (!sar?.narrative_summary) return;
    const blob = new Blob([sar.narrative_summary], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sar.sar_id || 'SAR_Report'}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleSendMessage = async (customQuery) => {
    const queryText = customQuery || inputQuery;
    if (!queryText.trim()) return;

    const userMsg = { role: 'user', content: queryText };
    setMessages((prev) => [...prev, userMsg]);
    if (!customQuery) setInputQuery('');
    setIsTyping(true);

    try {
      const res = await api.chat({
        query: queryText,
        transaction_context: tx,
        history: messages,
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: res.response }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '⚠️ Could not connect to AML Copilot assistant.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-fadeIn">
      <div 
        className="glass border border-white/15 bg-slate-950/90 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center gap-4">
            <div className="p-2.5 rounded-xl bg-violet-500/10 border border-violet-500/20 text-violet-400">
              <Bot size={24} />
            </div>
            <div>
              <div className="flex items-center gap-3">
                <h3 className="text-xl font-bold text-white">Autonomous Agent Investigation</h3>
                <span className={`px-3 py-1 rounded-full text-xs font-semibold border flex items-center gap-1.5 ${actionCfg.bg}`}>
                  <ActionIcon size={13} />
                  {actionCfg.label}
                </span>
                <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${
                  tier === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                  tier === 'HIGH' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' :
                  tier === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' :
                  'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                }`}>
                  {tier} RISK ({(proba * 100).toFixed(1)}%)
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Transaction: <span className="font-mono text-slate-300">{tx.nameOrig}</span> ➔ <span className="font-mono text-slate-300">{tx.nameDest}</span> · Amount: <strong className="text-white">${tx.amount?.toLocaleString()}</strong> · Channel: <span className="text-violet-300">{tx.type}</span>
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-white/10 transition"
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-white/10 px-6 bg-slate-900/30 text-sm">
          <button
            onClick={() => setActiveTab('summary')}
            className={`py-3 px-4 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === 'summary' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Sparkles size={16} />
            Diagnostic Analysis & Anomalies
          </button>
          <button
            onClick={() => setActiveTab('sar')}
            className={`py-3 px-4 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === 'sar' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <FileText size={16} />
            FinCEN SAR Narrative {sar && <span className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />}
          </button>
          <button
            onClick={() => setActiveTab('copilot')}
            className={`py-3 px-4 font-medium transition border-b-2 flex items-center gap-2 ${
              activeTab === 'copilot' 
                ? 'border-violet-500 text-white' 
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Bot size={16} />
            Compliance Copilot Chat
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto flex-1 space-y-6">
          {activeTab === 'summary' && (
            <div className="space-y-6">
              {/* Agent Reasoning Hero Card */}
              <div className="p-4 rounded-xl bg-violet-950/30 border border-violet-500/30">
                <div className="flex items-center gap-2 mb-2 text-violet-400 text-sm font-semibold">
                  <Bot size={16} />
                  Agent Synthesis & Containment Reasoning
                </div>
                <p className="text-sm text-slate-200 leading-relaxed">{reasoning}</p>
              </div>

              {/* Account Balance Ledger Breakdown */}
              <div>
                <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
                  <Activity size={15} className="text-violet-400" />
                  Ledger State & Counterparty Delta
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-xl bg-slate-900/60 border border-white/10">
                    <div className="text-xs text-slate-400 font-medium mb-1">Originator ({tx.nameOrig})</div>
                    <div className="flex items-center justify-between text-sm py-1 border-b border-white/5">
                      <span className="text-slate-400">Old Balance:</span>
                      <span className="font-mono text-slate-200">${tx.oldbalanceOrg?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-1 border-b border-white/5">
                      <span className="text-slate-400">Deduction:</span>
                      <span className="font-mono text-rose-400">-${tx.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-1 pt-2 font-bold">
                      <span className="text-slate-300">New Balance:</span>
                      <span className={`font-mono ${tx.newbalanceOrig === 0 ? 'text-red-400 font-extrabold' : 'text-slate-200'}`}>
                        ${tx.newbalanceOrig?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        {tx.oldbalanceOrg > 0 && tx.newbalanceOrig === 0 && ' (DRAINED)'}
                      </span>
                    </div>
                  </div>

                  <div className="p-4 rounded-xl bg-slate-900/60 border border-white/10">
                    <div className="text-xs text-slate-400 font-medium mb-1">Beneficiary ({tx.nameDest})</div>
                    <div className="flex items-center justify-between text-sm py-1 border-b border-white/5">
                      <span className="text-slate-400">Old Balance:</span>
                      <span className="font-mono text-slate-200">${tx.oldbalanceDest?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-1 border-b border-white/5">
                      <span className="text-slate-400">Credit Amount:</span>
                      <span className="font-mono text-emerald-400">+${tx.amount?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</span>
                    </div>
                    <div className="flex items-center justify-between text-sm py-1 pt-2 font-bold">
                      <span className="text-slate-300">New Balance:</span>
                      <span className="font-mono text-slate-200">
                        ${tx.newbalanceDest?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        {tx.oldbalanceDest === 0 && tx.newbalanceDest === 0 && ' (MULE SINK)'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Detected Risk Factors */}
              <div>
                <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
                  Identified Red Flags & Anomaly Decompositions ({factors.length})
                </h4>
                <div className="space-y-2.5">
                  {factors.map((f, i) => (
                    <div 
                      key={i} 
                      className="p-3.5 rounded-xl bg-slate-900/40 border border-white/10 flex items-start justify-between gap-4"
                    >
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-violet-400">{f.category}</span>
                          <span className="text-slate-600">·</span>
                          <span className="text-sm font-bold text-white">{f.factor}</span>
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed">{f.description}</p>
                      </div>
                      <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-bold border uppercase tracking-wide shrink-0 ${SEVERITY_BADGE[f.severity] || SEVERITY_BADGE.LOW}`}>
                        {f.severity}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {activeTab === 'sar' && (
            <div className="space-y-4">
              {sar ? (
                <>
                  <div className="flex items-center justify-between p-4 bg-slate-900/70 rounded-xl border border-white/10">
                    <div>
                      <div className="text-xs text-slate-400">SAR Reference Number</div>
                      <div className="text-base font-mono font-bold text-violet-400">{sar.sar_id}</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={handleCopySAR}
                        className="px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-xs font-medium text-white flex items-center gap-1.5 transition"
                      >
                        {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
                        {copied ? 'Copied!' : 'Copy Narrative'}
                      </button>
                      <button
                        onClick={handleDownloadSAR}
                        className="px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-xs font-medium text-white flex items-center gap-1.5 transition"
                      >
                        <Download size={14} />
                        Download Report (.txt)
                      </button>
                    </div>
                  </div>

                  <div className="p-4 bg-slate-950 rounded-xl border border-white/10 font-mono text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-96 overflow-y-auto">
                    {sar.narrative_summary}
                  </div>
                </>
              ) : (
                <div className="p-12 text-center text-slate-400 space-y-2">
                  <ShieldCheck size={40} className="mx-auto text-emerald-400 mb-2" />
                  <h4 className="text-base font-semibold text-white">No SAR Filing Required</h4>
                  <p className="text-xs max-w-md mx-auto">
                    This transaction scored {tier} Risk ({(proba * 100).toFixed(1)}%). Under FinCEN compliance guidelines, automated SAR generation is only triggered for HIGH or CRITICAL risk thresholds.
                  </p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'copilot' && (
            <div className="flex flex-col h-[400px] space-y-3">
              {/* Message Feed */}
              <div className="flex-1 bg-slate-950/60 p-4 rounded-xl border border-white/10 overflow-y-auto space-y-3">
                {messages.length === 0 && (
                  <div className="text-center py-8 space-y-3">
                    <Bot size={32} className="mx-auto text-violet-400" />
                    <p className="text-xs text-slate-300 max-w-md mx-auto">
                      Ask me anything regarding this transaction case, FinCEN regulations, or risk mitigation steps.
                    </p>
                    <div className="flex flex-wrap justify-center gap-2 pt-2">
                      {[
                        'Explain why this transaction was flagged',
                        'What are the SAR filing requirements for this case?',
                        'What containment action is recommended?',
                      ].map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSendMessage(prompt)}
                          className="px-3 py-1.5 rounded-full text-xs bg-violet-500/10 hover:bg-violet-500/20 text-violet-300 border border-violet-500/30 transition text-left"
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {messages.map((m, idx) => (
                  <div
                    key={idx}
                    className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[80%] p-3.5 rounded-2xl text-xs leading-relaxed ${
                        m.role === 'user'
                          ? 'bg-violet-600 text-white rounded-br-none'
                          : 'bg-slate-900 border border-white/10 text-slate-200 rounded-bl-none prose prose-invert'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{m.content}</div>
                    </div>
                  </div>
                ))}

                {isTyping && (
                  <div className="flex justify-start">
                    <div className="p-3 rounded-xl bg-slate-900 border border-white/10 text-xs text-slate-400 flex items-center gap-2">
                      <Bot size={14} className="animate-spin text-violet-400" />
                      Agent analyzing transaction features...
                    </div>
                  </div>
                )}
              </div>

              {/* Chat Input */}
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="Ask AML Copilot about this case..."
                  value={inputQuery}
                  onChange={(e) => setInputQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  className="flex-1 bg-slate-900 border border-white/10 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-violet-500 transition"
                />
                <button
                  onClick={() => handleSendMessage()}
                  disabled={!inputQuery.trim() || isTyping}
                  className="px-4 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold flex items-center gap-1.5 transition disabled:opacity-50"
                >
                  <Send size={14} />
                  Ask
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
