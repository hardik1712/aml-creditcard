import React, { useState } from 'react';
import { Bot, Send, Sparkles, Shield, RefreshCw, MessageSquare, AlertCircle } from 'lucide-react';
import { api } from '../api';

const QUICK_PROMPTS = [
  { label: 'Smurfing & Structuring', prompt: 'How does the pipeline identify smurfing and structuring patterns?' },
  { label: 'FinCEN SAR Thresholds', prompt: 'What are the statutory FinCEN SAR filing thresholds and rules?' },
  { label: 'ML Feature Importance', prompt: 'Which features are most predictive in the LightGBM fraud model?' },
  { label: 'Autonomous Actions', prompt: 'Explain the difference between FREEZE_ACCOUNT and BLOCK_TRANSACTION containment actions.' },
];

export default function AgentCopilot() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: (
        "### 🛡️ Welcome to AML Sentinel Copilot\n\n" +
        "I am your autonomous compliance assistant. I monitor transaction pipelines, explain LightGBM risk models, " +
        "assess Bank Secrecy Act (BSA) & FinCEN compliance, and assist in drafting Suspicious Activity Reports (SARs).\n\n" +
        "Select a topic below or type your question!"
      ),
    },
  ]);
  const [inputQuery, setInputQuery] = useState('');
  const [isTyping, setIsTyping] = useState(false);

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
        history: messages,
      });
      setMessages((prev) => [...prev, { role: 'assistant', content: res.response }]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '⚠️ Error connecting to the AML Copilot assistant service.' },
      ]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleClear = () => {
    setMessages([
      {
        role: 'assistant',
        content: "### 🛡️ Conversation reset.\n\nHow can I help you with your AML investigation today?",
      },
    ]);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Bot className="text-violet-400" />
            AML Compliance Copilot
          </h2>
          <p className="text-slate-400 text-sm">
            AI-powered regulatory reasoning, fraud pattern investigation, and SAR guidance.
          </p>
        </div>
        <button
          onClick={handleClear}
          className="px-3 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-400 hover:text-white text-xs font-medium flex items-center gap-1.5 transition"
        >
          <RefreshCw size={13} />
          Reset Chat
        </button>
      </div>

      {/* Main Chat Container */}
      <div className="glass rounded-2xl border border-white/10 flex flex-col h-[580px] overflow-hidden">
        {/* Messages Feed */}
        <div className="flex-1 p-6 overflow-y-auto space-y-4 bg-slate-950/40">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] p-4 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-violet-600 text-white rounded-br-none shadow-lg shadow-violet-600/20'
                    : 'bg-slate-900/90 border border-white/10 text-slate-200 rounded-bl-none shadow-md'
                }`}
              >
                <div className="whitespace-pre-wrap">{m.content}</div>
              </div>
            </div>
          ))}

          {isTyping && (
            <div className="flex justify-start">
              <div className="p-3.5 rounded-2xl bg-slate-900 border border-white/10 text-xs text-slate-400 flex items-center gap-2">
                <Bot size={16} className="animate-spin text-violet-400" />
                Copilot is reviewing compliance policies and transaction models...
              </div>
            </div>
          )}
        </div>

        {/* Quick Prompts Bar */}
        <div className="p-3 bg-slate-900/80 border-t border-white/5 flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-slate-400 flex items-center gap-1 shrink-0 font-medium pl-2">
            <Sparkles size={13} className="text-violet-400" />
            Quick Prompts:
          </span>
          {QUICK_PROMPTS.map((qp, idx) => (
            <button
              key={idx}
              onClick={() => handleSendMessage(qp.prompt)}
              className="px-3 py-1 rounded-full text-xs bg-white/5 hover:bg-violet-500/20 hover:text-violet-300 text-slate-300 border border-white/10 shrink-0 transition"
            >
              {qp.label}
            </button>
          ))}
        </div>

        {/* Input Bar */}
        <div className="p-4 bg-slate-900/90 border-t border-white/10 flex items-center gap-3">
          <input
            type="text"
            placeholder="Ask about fraud models, transaction anomalies, or FinCEN SAR rules..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            className="flex-1 bg-slate-950 border border-white/10 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-violet-500 transition placeholder:text-slate-500"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!inputQuery.trim() || isTyping}
            className="px-5 py-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-sm flex items-center gap-2 transition disabled:opacity-50 shadow-lg shadow-violet-600/30"
          >
            <Send size={15} />
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
