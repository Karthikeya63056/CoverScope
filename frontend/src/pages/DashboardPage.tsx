import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  FileText,
  MessageSquare,
  ShieldCheck,
  ArrowRight,
  Upload,
  Scale,
  GitCompare,
  Sparkles,
  Database,
  ClipboardCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  ExternalLink,
  Trash2,
  Lock,
  Download,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { DashboardSummaryResponse } from '../lib/types';
import { useAuth } from '../context/AuthContext';

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function loadSummary() {
      try {
        const res = await api.getDashboardSummary();
        setData(res);
      } catch (err) {
        console.warn('Failed to load dashboard summary:', err);
      } finally {
        setIsLoading(false);
      }
    }
    loadSummary();
  }, []);

  const handleDeletePolicy = async (id: string, name: string) => {
    if (
      !window.confirm(
        `Permanently delete policy "${name}" from your MongoDB database and storage?\n\nThis will purge the file, indexed chunks, and analysis records. This cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.deletePolicy(id);
      if (data) {
        setData({
          ...data,
          total_policies: Math.max(0, data.total_policies - 1),
          recent_policies: data.recent_policies.filter((p) => (p.policy_id || p.id) !== id && p.id !== id),
        });
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete policy.');
    }
  };

  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownloadPolicy = async (id: string, name: string) => {
    try {
      setDownloadingId(id);
      const blob = await api.downloadPolicy(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name.endsWith('.pdf') ? name : `${name}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err.message || 'Failed to download policy PDF.');
    } finally {
      setDownloadingId(null);
    }
  };

  const displayName = user?.display_name || user?.email?.split('@')[0] || '';

  return (
    <div className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Welcome Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-slate-900 p-6 sm:p-8 text-white shadow-sm border border-slate-800">
        <div className="relative z-10 max-w-2xl">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20 mb-3">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Grounded Policy Intelligence</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            {displayName ? `Welcome back, ${displayName}` : 'Welcome to CoverScope'}
          </h1>
          <p className="mt-2 text-xs sm:text-sm text-slate-300 leading-relaxed max-w-xl">
            Query your policy schedules with verifiable page citations, simulate medical claims against
            waiting periods, and rehearse pre-admission hospitalizations with zero hallucination.
          </p>
          <div className="mt-5 flex flex-wrap gap-2.5">
            <Link
              to="/ask"
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 transition"
            >
              <MessageSquare className="h-3.5 w-3.5" />
              <span>Ask My Policy</span>
            </Link>
            <Link
              to="/claim-rehearsal"
              className="inline-flex items-center gap-2 rounded-lg bg-slate-800 border border-slate-700 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700 transition"
            >
              <ClipboardCheck className="h-3.5 w-3.5 text-emerald-400" />
              <span>Rehearse a Claim</span>
            </Link>
            <Link
              to="/library"
              className="inline-flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Upload Schedule</span>
            </Link>
          </div>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Active Policies */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Active Policies
            </span>
            <div className="rounded-lg bg-emerald-50 p-2 text-emerald-600">
              <FileText className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {isLoading ? '...' : data?.total_policies ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">Loaded schedules &amp; brochures</p>
        </div>

        {/* Consultations */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Consultations
            </span>
            <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
              <MessageSquare className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {isLoading ? '...' : data?.total_conversations ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">Grounded Q&amp;A sessions</p>
        </div>

        {/* Analyses Run */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Analyses Run
            </span>
            <div className="rounded-lg bg-purple-50 p-2 text-purple-600">
              <Scale className="h-4 w-4" />
            </div>
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">
            {isLoading ? '...' : data?.total_analyses ?? 0}
          </p>
          <p className="mt-1 text-xs text-slate-500">Scenarios &amp; claim rehearsals</p>
        </div>

        {/* Database Status */}
        <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Cluster Sync
            </span>
            <div className="rounded-lg bg-teal-50 p-2 text-teal-600">
              <Database className="h-4 w-4" />
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                data?.database_status === 'connected'
                  ? 'bg-emerald-500 animate-pulse'
                  : data?.database_status === 'not_configured'
                  ? 'bg-amber-400'
                  : 'bg-rose-500'
              }`}
            />
            <p className="text-sm font-semibold text-slate-800">
              {data?.database_status === 'connected'
                ? 'MongoDB Atlas Live'
                : data?.database_status === 'not_configured'
                ? 'Offline Memory Mode'
                : 'Cluster Offline'}
            </p>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            {data?.database_status === 'connected'
              ? 'Multi-tenant cloud persistence'
              : 'Local session cache'}
          </p>
        </div>
      </div>

      {/* Quick Action Hub */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-500">
            Insurance Intelligence Hub
          </h2>
          <span className="text-xs text-slate-400">Select a tool to begin</span>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {/* Ask My Policy */}
          <Link
            to="/ask"
            className="group relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition hover:border-emerald-500 hover:shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 transition group-hover:scale-105">
                <MessageSquare className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-emerald-700">
                Ask My Policy
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Inquire about specific medical treatments, organ donor cover, or waiting periods with verified page citations.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-emerald-600">
              <span>Ask question</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>

          {/* Claim Rehearsal */}
          <Link
            to="/claim-rehearsal"
            className="group relative rounded-xl border border-emerald-200/90 bg-emerald-50/20 p-5 shadow-xs transition hover:border-emerald-500 hover:shadow-md flex flex-col justify-between"
          >
            <span className="absolute top-4 right-4 rounded-full bg-emerald-600 px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-white">
              Feature
            </span>
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800 transition group-hover:scale-105">
                <ClipboardCheck className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-emerald-700">
                Claim Rehearsal
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Simulate planned hospitalizations against waiting periods, room-rent limits, co-payments, and pre-auth checklists.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-emerald-700">
              <span>Rehearse claim</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>

          {/* Scenario Analyzer */}
          <Link
            to="/scenarios"
            className="group relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition hover:border-teal-500 hover:shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-50 text-teal-700 transition group-hover:scale-105">
                <Scale className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-teal-700">
                Scenario Analyzer
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Deterministically test pre-existing conditions, elapsed duration, and age-based co-payments.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-teal-600">
              <span>Run scenario</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>

          {/* Policy Comparison */}
          <Link
            to="/compare"
            className="group relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition hover:border-blue-500 hover:shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700 transition group-hover:scale-105">
                <GitCompare className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-blue-700">
                Policy Comparison
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Perform dimensional analysis across 2 policies to reveal hidden sublimits, co-payments, and protection gaps.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-blue-600">
              <span>Compare policies</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>

          {/* Policy Explorer */}
          <Link
            to="/explorer"
            className="group relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition hover:border-slate-400 hover:shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-700 transition group-hover:scale-105">
                <ExternalLink className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-slate-800">
                Policy Explorer
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Inspect raw page-by-page text extracts, chunk distributions, and extracted candidate policy facts.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-slate-600">
              <span>Explore clauses</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>

          {/* Document Library */}
          <Link
            to="/library"
            className="group relative rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs transition hover:border-slate-400 hover:shadow-md flex flex-col justify-between"
          >
            <div>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-700 transition group-hover:scale-105">
                <Upload className="h-5 w-5" />
              </div>
              <h3 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-amber-800">
                Document Library
              </h3>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                Upload new health insurance policy PDF schedules, review extraction quality, or delete documents.
              </p>
            </div>
            <div className="mt-4 flex items-center gap-1 text-xs font-semibold text-amber-700">
              <span>Manage documents</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
            </div>
          </Link>
        </div>
      </div>

      {/* Loaded Policy Documents Section */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
          <div>
            <h2 className="text-base font-bold text-slate-900">Loaded Policy Documents</h2>
            <p className="text-xs text-slate-500">
              Verified documents active in memory and ready for immediate consultation
            </p>
          </div>
          <Link
            to="/library"
            className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 hover:text-emerald-700"
          >
            <span>Manage Library</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {data?.recent_policies && data.recent_policies.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/75 border-b border-slate-200 text-slate-600">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">Policy Document</th>
                  <th className="py-2.5 px-3 font-semibold">Pages</th>
                  <th className="py-2.5 px-3 font-semibold">Indexed Chunks</th>
                  <th className="py-2.5 px-3 font-semibold">Source Status</th>
                  <th className="py-2.5 px-3 font-semibold text-right">Quick Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {data.recent_policies.map((p) => {
                  const name = p.filename || p.document_name || 'Policy Document';
                  const id = p.policy_id || p.id || '';
                  const chunks = p.total_chunks ?? p.metadata?.chunk_count ?? 0;
                  const status = p.status || p.processing_status || 'processed';
                  const isBundled = (status === 'bundled' || p.status === 'bundled');

                  return (
                    <tr key={id || name} className="hover:bg-slate-50/60 transition-colors">
                      <td className="py-3 px-3 font-medium text-slate-900 flex items-center gap-2">
                        <FileText className={`h-4 w-4 shrink-0 ${isBundled ? 'text-blue-600' : 'text-emerald-600'}`} />
                        <span className="truncate max-w-xs sm:max-w-md font-semibold">{name}</span>
                      </td>
                      <td className="py-3 px-3 text-slate-600">{p.page_count ?? 1} pages</td>
                      <td className="py-3 px-3 text-slate-600">{chunks} chunks</td>
                      <td className="py-3 px-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize ${
                          isBundled ? 'bg-blue-50 text-blue-700' : 'bg-emerald-50 text-emerald-700'
                        }`}>
                          {isBundled ? 'Demo Policy' : status}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right space-x-2">
                        <Link
                          to={`/claim-rehearsal?policy=${encodeURIComponent(id)}`}
                          className="font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                        >
                          Rehearse
                        </Link>
                        <span className="text-slate-300">•</span>
                        <Link
                          to={`/ask?policy=${encodeURIComponent(id)}`}
                          className="font-semibold text-slate-700 hover:text-slate-900 hover:underline"
                        >
                          Ask
                        </Link>
                        <span className="text-slate-300">•</span>
                        <Link
                          to={`/explorer?policy=${encodeURIComponent(id)}`}
                          className="text-slate-500 hover:text-slate-800 hover:underline"
                        >
                          Explore
                        </Link>
                        <span className="text-slate-300">•</span>
                        <button
                          onClick={() => handleDownloadPolicy(id, name)}
                          disabled={downloadingId === id}
                          title="Download original verified PDF policy document"
                          className="font-semibold text-slate-700 hover:text-slate-900 hover:underline inline-flex items-center gap-0.5 disabled:opacity-50"
                        >
                          <Download className="h-3 w-3 inline text-emerald-600" />
                          <span>{downloadingId === id ? 'Downloading...' : 'PDF'}</span>
                        </button>
                        {!isBundled && (
                          <>
                            <span className="text-slate-300">•</span>
                            <button
                              onClick={() => handleDeletePolicy(id, name)}
                              title="Delete policy from database and storage"
                              className="font-semibold text-rose-600 hover:text-rose-700 hover:underline inline-flex items-center gap-0.5"
                            >
                              <Trash2 className="h-3 w-3 inline" />
                              <span>Delete</span>
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-slate-200 p-8 text-center bg-slate-50/50">
            <FileText className="mx-auto h-8 w-8 text-slate-300" />
            <p className="mt-2 text-sm font-semibold text-slate-700">No policy documents loaded</p>
            <p className="mt-1 text-xs text-slate-500">
              Upload your health insurance schedule PDF to begin asking questions and rehearsing claims
            </p>
            <Link
              to="/library"
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 transition"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Upload Policy Schedule</span>
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};
