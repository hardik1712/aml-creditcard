import { useState } from 'react';
import Sidebar from './components/Sidebar';
import AgentPipeline from './pages/AgentPipeline';
import AgentCopilot from './components/AgentCopilot';
import Overview from './pages/Overview';
import Scorer from './pages/Scorer';
import FileUpload from './pages/FileUpload';

const PAGES = {
  pipeline: <AgentPipeline />,
  copilot:  <AgentCopilot />,
  overview: <Overview />,
  upload:   <FileUpload />,
  scorer:   <Scorer />,
};

export default function App() {
  const [page, setPage] = useState('pipeline');

  return (
    <div className="flex min-h-screen">
      <Sidebar active={page} onNavigate={setPage} />

      <main className="flex-1 py-10 px-8 lg:px-12 max-w-6xl">
        {/* Page header */}
        <header className="mb-8 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="gradient-text text-4xl font-extrabold tracking-tight mb-2">
              AML Autonomous Sentinel
            </h1>
            <p className="text-slate-400 text-base">
              Agentic fraud containment, automated stream ingestion, and real-time FinCEN compliance.
            </p>
          </div>
        </header>

        {/* Active page */}
        <div key={page} className="animate-fadeIn">
          {PAGES[page]}
        </div>
      </main>
    </div>
  );
}

