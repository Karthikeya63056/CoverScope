import React from 'react';
import { Outlet } from 'react-router-dom';
import { Navbar } from '../components/Navbar';
import { ShieldCheck, Database, FileText, ClipboardCheck } from 'lucide-react';

export const AppLayout: React.FC = () => {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50/50">
      <Navbar />

      <main className="flex-1 py-8 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto w-full">
        <Outlet />
      </main>

      <footer className="mt-auto border-t border-slate-200/80 bg-white py-6">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 text-xs text-slate-500 sm:flex-row sm:px-6 lg:px-8">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">CoverScope</span>
            <span>&copy; {new Date().getFullYear()} Policy Intelligence Platform</span>
          </div>

          <div className="flex flex-wrap items-center justify-center gap-4 text-slate-400">
            <span className="flex items-center gap-1">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
              Evidence-Grounded Citations
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <ClipboardCheck className="h-3.5 w-3.5 text-emerald-600" />
              Claim Rehearsal
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <Database className="h-3.5 w-3.5 text-teal-600" />
              MongoDB Atlas Persisted
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <FileText className="h-3.5 w-3.5 text-blue-600" />
              Verbatim Policy Clauses
            </span>
          </div>

          <div className="text-[11px] text-slate-400 text-center sm:text-right">
            Not legal or insurance advice. Always verify with your official policy schedule.
          </div>
        </div>
      </footer>
    </div>
  );
};
