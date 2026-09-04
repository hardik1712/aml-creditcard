import { useEffect, useState } from 'react';
import { Shield, Activity } from 'lucide-react';
import { api } from '../api';

const NAV_ITEMS = [
  { id: 'pipeline',   label: 'Agentic Pipeline',    emoji: '🤖' },
  { id: 'copilot',    label: 'Compliance Copilot',  emoji: '💬' },
  { id: 'overview',   label: 'Overview & KPIs',     emoji: '📊' },
  { id: 'upload',     label: 'Batch File Ingestion',emoji: '📁' },
  { id: 'scorer',     label: 'Transaction Scorer',  emoji: '🔍' },
];

export default function Sidebar({ active, onNavigate }) {
  const [status, setStatus] = useState('checking'); // checking | online | offline

  useEffect(() => {
    api.health()
      .then(() => setStatus('online'))
      .catch(() => setStatus('offline'));
  }, []);

  const dotColor = {
    checking: 'bg-amber-400 animate-pulse-slow',
    online:   'bg-green-400',
    offline:  'bg-red-500',
  }[status];

  const statusLabel = {
    checking: 'Checking API…',
    online:   'API Online',
    offline:  'API Offline',
  }[status];

  return (
    <aside className="glass m-4 p-6 flex flex-col w-72 shrink-0 sticky top-4 h-[calc(100vh-2rem)]">
      {/* Brand */}
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-3">
          <Shield className="text-violet-400" size={24} />
          <h2 className="text-xl font-extrabold tracking-tight">AML Detector</h2>
        </div>

        {/* API Status pill */}
        <div className="flex items-center gap-2 bg-black/20 rounded-full px-3 py-1.5 w-fit text-sm text-slate-400">
          <span className={`w-2.5 h-2.5 rounded-full ${dotColor}`} />
          <span>{statusLabel}</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-2 flex-1">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onNavigate(item.id)}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl text-left text-sm font-medium transition-all duration-300 ${
              active === item.id
                ? 'bg-white/10 text-white border-l-4 border-violet-500 pl-3 shadow-[0_0_15px_rgba(139,92,246,0.25)]'
                : 'text-slate-400 hover:text-white hover:bg-white/5 hover:translate-x-1.5'
            }`}
          >
            <span className="text-base">{item.emoji}</span>
            {item.label}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="text-xs text-slate-500 mt-4 space-y-0.5">
        <div className="flex items-center gap-1">
          <Activity size={12} />
          <span>AML Fraud Detection v1.0</span>
        </div>
        <div>React + Vite + FastAPI</div>
      </div>
    </aside>
  );
}
