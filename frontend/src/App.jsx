import { useState } from 'react';
import Sidebar from './components/Sidebar';
import Overview from './pages/Overview';
import Scorer from './pages/Scorer';

const PAGES = {
  overview: <Overview />,
  scorer:   <Scorer />,
};

export default function App() {
  const [page, setPage] = useState('overview');

  return (
    <div className="flex min-h-screen">
      <Sidebar active={page} onNavigate={setPage} />

      <main className="flex-1 py-8 pr-10 pl-4 max-w-5xl">
        {/* Page header */}
        <header className="mb-10">
          <h1 className="gradient-text text-4xl font-extrabold tracking-tight mb-1">
            AML Fraud Detection Dashboard
          </h1>
          <p className="text-slate-400 text-lg">Real-time monitoring and analysis of transaction fraud risk</p>
        </header>

        {/* Active page */}
        <div key={page}>
          {PAGES[page]}
        </div>
      </main>
    </div>
  );
}
