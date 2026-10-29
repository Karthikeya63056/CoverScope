import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  GitCompare,
  AlertTriangle,
  CheckCircle2,
  AlertCircle,
  ShieldAlert,
  ArrowRight,
  Sliders,
  Scale,
  FileText,
  FileCheck2,
  UploadCloud,
  Check,
  Layers,
  Sparkles,
  LayoutGrid,
  Table as TableIcon,
  MinusCircle,
  Info,
  Ban,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, ComparisonResponse, ProtectionGapItem } from '../lib/types';

export const ComparisonPage: React.FC = () => {
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [policyAId, setPolicyAId] = useState<string>('');
  const [policyBId, setPolicyBId] = useState<string>('');
  const [continuousMonths, setContinuousMonths] = useState<number>(24);
  const [entryAge, setEntryAge] = useState<number>(40);

  const [isLoadingPolicies, setIsLoadingPolicies] = useState(true);
  const [isComparing, setIsComparing] = useState(false);
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Allow custom event for automated UI/UX verification
  useEffect(() => {
    const handleSetMock = (e: any) => {
      if (e.detail) setResult(e.detail);
    };
    window.addEventListener('coverscope-compare-result', handleSetMock);
    return () => window.removeEventListener('coverscope-compare-result', handleSetMock);
  }, []);

  // Presentation states for comparison matrix
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards');
  const [statusFilter, setStatusFilter] = useState<'all' | 'gaps' | 'comparable'>('all');
  const [showGapsList, setShowGapsList] = useState<boolean>(true);

  useEffect(() => {
    async function loadPolicies() {
      try {
        const res = await api.listPolicies();
        const list = res.policies || [];
        setPolicies(list);
        if (list.length >= 2) {
          setPolicyAId(list[0].policy_id || list[0].id || '');
          setPolicyBId(list[1].policy_id || list[1].id || '');
        } else if (list.length === 1) {
          const id = list[0].policy_id || list[0].id || '';
          setPolicyAId(id);
          setPolicyBId('');
        }
      } catch (err: any) {
        setErrorMsg('Failed to load policies.');
      } finally {
        setIsLoadingPolicies(false);
      }
    }
    loadPolicies();
  }, []);

  const handleCompare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!policyAId || !policyBId) {
      setErrorMsg('Please select two policies to compare.');
      return;
    }
    if (policyAId === policyBId) {
      setErrorMsg('Self-comparison detected: Please select two distinct policy schedules to uncover protection gaps.');
      return;
    }

    setIsComparing(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const res = await api.comparePolicies({
        policy_id_a: policyAId,
        policy_id_b: policyBId,
        continuous_months: Number(continuousMonths),
        member_age: Number(entryAge),
      });
      setResult(res);
    } catch (err: any) {
      setErrorMsg(err.message || 'Comparison failed.');
    } finally {
      setIsComparing(false);
    }
  };

  const formatPolicyDisplayName = (fullName?: string, fallback: string = 'Policy') => {
    if (!fullName) return fallback;
    let clean = fullName.replace(/\.pdf$/i, '');
    clean = clean.replace(/_/g, ' ');
    clean = clean.replace(/\s+[a-f0-9]{8,}$/i, '');
    return clean.trim();
  };

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'comparable') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800 border border-emerald-200/60">
          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
          Comparable Terms
        </span>
      );
    }
    if (s === 'condition_dependent') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 border border-amber-200/60">
          <Scale className="h-3 w-3 text-amber-600" />
          Condition Dependent
        </span>
      );
    }
    if (s === 'missing_from_documents') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold text-slate-700 border border-slate-200/60">
          <MinusCircle className="h-3 w-3 text-slate-500" />
          Missing From Documents
        </span>
      );
    }
    if (s === 'needs_review') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-[10px] font-bold text-blue-800 border border-blue-200/60">
          <Info className="h-3 w-3 text-blue-600" />
          Needs Review
        </span>
      );
    }
    if (s === 'not_applicable') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-600 border border-slate-200/60">
          Not Applicable
        </span>
      );
    }
    return (
      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
        {status}
      </span>
    );
  };

  const getGapSeverityBadge = (severity: string) => {
    const s = severity.toLowerCase();
    if (s === 'caution') {
      return (
        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-800 border border-rose-200/60">
          Caution
        </span>
      );
    }
    if (s === 'conditional_gap') {
      return (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-800 border border-amber-200/60">
          Conditional Gap
        </span>
      );
    }
    if (s === 'unverified_gap') {
      return (
        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-800 border border-blue-200/60">
          Unverified Gap
        </span>
      );
    }
    return (
      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700 border border-slate-200/60">
        Informational
      </span>
    );
  };

  const PolicyValueDisplay: React.FC<{ value: string; isPolicyA?: boolean }> = ({ value, isPolicyA }) => {
    if (!value) {
      return <span className="text-slate-400 italic text-xs">Not recorded</span>;
    }

    const v = value.trim();
    const lower = v.toLowerCase();

    if (lower.includes('not found in policy text') || lower.includes('not documented')) {
      return (
        <div className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-500 border border-slate-200/60">
          <MinusCircle className="h-3.5 w-3.5 text-slate-400 shrink-0" />
          <span>Not found in policy text</span>
        </div>
      );
    }

    if (lower.includes('requires policy schedule')) {
      return (
        <div className="inline-flex items-center gap-1.5 rounded-lg bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-900 border border-amber-200/80">
          <FileText className="h-3.5 w-3.5 text-amber-600 shrink-0" />
          <span>Requires Policy Schedule</span>
        </div>
      );
    }

    if (lower.includes('standard exclusion')) {
      return (
        <div className="space-y-1">
          <div className="inline-flex items-center gap-1.5 rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-800 border border-rose-200/70">
            <Ban className="h-3.5 w-3.5 text-rose-600 shrink-0" />
            <span>Standard Exclusion</span>
          </div>
          {v.includes('(') && (
            <p className="text-[11px] font-mono text-slate-500">
              {v.substring(v.indexOf('('))}
            </p>
          )}
        </div>
      );
    }

    // Values with optional rider or notes in parentheses
    if (v.includes('(')) {
      const main = v.substring(0, v.indexOf('(')).trim();
      const sub = v.substring(v.indexOf('(')).trim();

      return (
        <div className="space-y-1">
          <p className={`text-xs font-bold leading-snug ${isPolicyA ? 'text-emerald-950' : 'text-blue-950'}`}>
            {main}
          </p>
          <span className="inline-block text-[11px] font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md border border-slate-200/60">
            {sub.replace(/^\(|\)$/g, '')}
          </span>
        </div>
      );
    }

    return (
      <p className={`text-xs font-bold leading-snug ${isPolicyA ? 'text-emerald-950' : 'text-blue-950'}`}>
        {v}
      </p>
    );
  };

  const renderAssessment = (assessment: string, nameA?: string, nameB?: string) => {
    if (!assessment) return null;

    let cleanText = assessment;
    if (nameA) {
      cleanText = cleanText.split(nameA).join('Policy A');
    }
    if (nameB) {
      cleanText = cleanText.split(nameB).join('Policy B');
    }

    const isIdentical =
      cleanText.toLowerCase().includes('identical') ||
      cleanText.toLowerCase().includes('both policies specify');
    const isAdvantage =
      cleanText.toLowerCase().includes('lower co-payment') ||
      cleanText.toLowerCase().includes('establishes') ||
      cleanText.toLowerCase().includes('higher');
    const isMissingBoth = cleanText.toLowerCase().includes('neither policy document');

    let bannerClass = 'bg-slate-50 border-slate-200/80 text-slate-700';
    let icon = <Info className="h-4 w-4 text-slate-500 shrink-0 mt-0.5" />;
    let tag = 'Audited Clause';
    let tagClass = 'bg-slate-200/80 text-slate-700 font-semibold';

    if (isIdentical) {
      bannerClass = 'bg-emerald-50/70 border-emerald-200/80 text-emerald-900';
      icon = <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />;
      tag = 'Parity • Identical Terms';
      tagClass = 'bg-emerald-100 text-emerald-800 font-bold';
    } else if (isAdvantage) {
      bannerClass = 'bg-amber-50/70 border-amber-200/80 text-amber-900';
      icon = <Scale className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />;
      tag = 'Coverage Divergence';
      tagClass = 'bg-amber-100 text-amber-800 font-bold';
    } else if (isMissingBoth) {
      bannerClass = 'bg-slate-50 border-slate-200/80 text-slate-600';
      icon = <AlertCircle className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />;
      tag = 'Unverified in Both';
      tagClass = 'bg-slate-200/80 text-slate-600 font-semibold';
    }

    return (
      <div className={`flex items-start gap-2.5 rounded-xl border p-3 text-xs leading-relaxed ${bannerClass}`}>
        {icon}
        <div className="space-y-0.5 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`rounded px-1.5 py-0.2 text-[9px] uppercase tracking-wider ${tagClass}`}>
              {tag}
            </span>
            <span className="text-[11px] font-bold">Clause Takeaway</span>
          </div>
          <p className="font-medium text-xs leading-relaxed">{cleanText}</p>
        </div>
      </div>
    );
  };

  const policyA = policies.find((p) => (p.policy_id || p.id) === policyAId);
  const policyB = policies.find((p) => (p.policy_id || p.id) === policyBId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1.5">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/20 bg-emerald-50/60 px-3 py-1 text-xs font-semibold text-emerald-800">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Deterministic Dimensional Matrix</span>
          <span className="text-slate-300">•</span>
          <span className="text-slate-600 font-normal">Side-by-Side Protection Gap Auditing</span>
        </div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Cross-Policy Comparison</h1>
        <p className="text-sm text-slate-500 max-w-3xl">
          Side-by-side dimensional matrix comparing 2 health insurance contracts. Automatically uncovers hidden sublimits, waiting period discrepancies, and protection gaps.
        </p>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 animate-in fade-in-50">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span className="font-medium">{errorMsg}</span>
        </div>
      )}

      {/* Notice when fewer than 2 policies are available */}
      {policies.length < 2 && (
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 rounded-xl border border-amber-200/90 bg-amber-50/70 p-4 text-xs text-amber-900 shadow-2xs">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
            <div className="space-y-0.5">
              <p className="font-bold">Two distinct policy schedules required for comparative audit</p>
              <p className="text-amber-800 leading-relaxed text-[11px]">
                You currently have {policies.length} policy in your document index. Upload a second policy schedule to evaluate side-by-side protection gaps.
              </p>
            </div>
          </div>
          <Link
            to="/library"
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-800 px-3 py-1.5 text-xs font-bold text-white hover:bg-amber-900 transition shrink-0 shadow-xs"
          >
            <UploadCloud className="h-3.5 w-3.5" />
            <span>Upload Policy B</span>
          </Link>
        </div>
      )}

      {/* Configuration Card */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs">
        <form onSubmit={handleCompare} className="space-y-5">
          {/* Form Header */}
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                <GitCompare className="h-4 w-4" />
              </div>
              <div>
                <h2 className="text-sm font-bold text-slate-900">Comparative Contract Setup</h2>
                <p className="text-[11px] text-slate-500">Select two policy schedules and simulation parameters</p>
              </div>
            </div>
            <span className="hidden sm:inline-flex rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-600">
              Deterministic Gap Engine
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Policy A */}
            <div className="rounded-xl bg-emerald-50/40 p-4 border border-emerald-100/90 space-y-2">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-bold text-emerald-800 uppercase tracking-wider">
                  <FileText className="h-3.5 w-3.5 text-emerald-600" />
                  Baseline Policy (Policy A)
                </span>
                <span className="rounded bg-emerald-100/70 px-1.5 py-0.2 text-[9px] font-bold text-emerald-800">
                  Primary
                </span>
              </div>
              <select
                value={policyAId}
                onChange={(e) => setPolicyAId(e.target.value)}
                className="w-full rounded-xl border border-emerald-200 bg-white py-2 px-3 text-xs font-medium text-slate-800 shadow-2xs focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600 truncate"
              >
                {policies.map((p) => {
                  const id = p.policy_id || p.id || '';
                  const name = p.filename || p.document_name || 'Policy Document';
                  return (
                    <option key={id} value={id}>
                      {name} ({p.page_count ?? 1} pages)
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Policy B */}
            <div className="rounded-xl bg-blue-50/40 p-4 border border-blue-100/90 space-y-2">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[11px] font-bold text-blue-800 uppercase tracking-wider">
                  <FileCheck2 className="h-3.5 w-3.5 text-blue-600" />
                  Comparison Policy (Policy B)
                </span>
                <span className="rounded bg-blue-100/70 px-1.5 py-0.2 text-[9px] font-bold text-blue-800">
                  Benchmarked
                </span>
              </div>
              <select
                value={policyBId}
                onChange={(e) => setPolicyBId(e.target.value)}
                className="w-full rounded-xl border border-blue-200 bg-white py-2 px-3 text-xs font-medium text-slate-800 shadow-2xs focus:border-blue-600 focus:outline-hidden focus:ring-1 focus:ring-blue-600 truncate"
              >
                {policies.map((p) => {
                  const id = p.policy_id || p.id || '';
                  const name = p.filename || p.document_name || 'Policy Document';
                  return (
                    <option key={id} value={id}>
                      {name} ({p.page_count ?? 1} pages)
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          {/* Assumptions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-800">
                Continuous Coverage Duration (Months)
              </label>
              <div className="relative">
                <input
                  type="number"
                  min={0}
                  max={120}
                  value={continuousMonths}
                  onChange={(e) => setContinuousMonths(parseInt(e.target.value) || 0)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-3 pr-16 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                />
                <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-[10px] text-slate-400 font-medium pointer-events-none">
                  months
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Used to evaluate pre-existing condition and specific ailment waiting clocks
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-800">
                Insured Member Entry Age (Years)
              </label>
              <div className="relative">
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={entryAge}
                  onChange={(e) => setEntryAge(parseInt(e.target.value) || 0)}
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-3 pr-12 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                />
                <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-[10px] text-slate-400 font-medium pointer-events-none">
                  yrs
                </span>
              </div>
              <p className="text-[10px] text-slate-400">
                Determines age-tiered co-payments and premium loading rules
              </p>
            </div>
          </div>

          {/* Action Row */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-slate-100">
            <span className="text-[11px] text-slate-400 hidden sm:inline">
              Compares room rents, ICU sub-limits, PED waiting periods, and copays
            </span>

            <button
              type="submit"
              disabled={isComparing || !policyAId || !policyBId || policyAId === policyBId}
              className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-6 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 hover:shadow-md disabled:opacity-50 transition-all cursor-pointer"
            >
              {isComparing ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Comparing Policy Dimensions...</span>
                </>
              ) : (
                <>
                  <GitCompare className="h-3.5 w-3.5" />
                  <span>Run Comparison</span>
                  <ArrowRight className="h-3.5 w-3.5 ml-0.5" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Feature Showcase when no comparison has been run yet */}
      {!result && (
        <div className="rounded-2xl border border-slate-200/80 bg-white p-8 text-center space-y-6 shadow-2xs">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-600">
            <Layers className="h-6 w-6" />
          </div>
          <div className="max-w-md mx-auto space-y-1">
            <h3 className="text-base font-bold text-slate-900">Side-by-Side Protection Gap Detection</h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              CoverScope compares policy clauses across critical dimensions to reveal subtle terms that affect out-of-pocket expenses.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-left">
            <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-emerald-700 font-bold text-xs">
                <Check className="h-4 w-4 shrink-0 text-emerald-600" />
                <span>Room Rent &amp; ICU Sub-Limits</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Detects 1% proportionate deduction clauses versus single private room coverage without penalties.
              </p>
            </div>

            <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-emerald-700 font-bold text-xs">
                <Check className="h-4 w-4 shrink-0 text-emerald-600" />
                <span>Waiting Period Arbitrage</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Compares 24m, 36m, and 48m pre-existing disease (PED) and specific illness exclusion timelines.
              </p>
            </div>

            <div className="rounded-xl border border-slate-100 bg-slate-50/60 p-4 space-y-1.5">
              <div className="flex items-center gap-2 text-emerald-700 font-bold text-xs">
                <Check className="h-4 w-4 shrink-0 text-emerald-600" />
                <span>Co-Payment Tiers</span>
              </div>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Audits mandatory senior citizen copays (e.g. 10–20% at age 61+) vs policies with zero member copay.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Comparison Results */}
      {result && (
        <div className="space-y-6">
          {/* Protection Gap Alerts */}
          {result.gaps && result.gaps.length > 0 && (
            <div className="rounded-2xl border border-amber-200/90 bg-amber-50/40 p-5 space-y-3.5 shadow-2xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100 text-amber-800">
                    <ShieldAlert className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-amber-950">
                      Detected Protection Gaps ({result.gaps.length})
                    </h3>
                    <p className="text-[11px] text-amber-800">
                      Discrepancies, waiting period gaps, and sub-limits identified across both contracts
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setShowGapsList(!showGapsList)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300/80 bg-white px-3 py-1 text-xs font-semibold text-amber-900 hover:bg-amber-50 transition cursor-pointer shadow-2xs"
                >
                  <span>{showGapsList ? 'Collapse Gaps' : 'Expand Gaps'}</span>
                  {showGapsList ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                </button>
              </div>

              {showGapsList && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1 animate-in fade-in-50 duration-200">
                  {result.gaps.map((gap, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-amber-200/80 bg-white p-4 shadow-2xs space-y-2 hover:border-amber-300 transition"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-bold text-xs text-amber-950 leading-snug">{gap.title}</span>
                        {getGapSeverityBadge(gap.severity)}
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{gap.description}</p>
                      <div className="pt-0.5 flex items-center gap-1.5 text-[10px] text-amber-700 font-mono">
                        <span className="rounded bg-amber-50 px-1.5 py-0.5 border border-amber-200/50">
                          Dimension: {gap.dimension}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Matrix Controls & Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pt-2">
            <div>
              <h3 className="text-base font-bold text-slate-900">Side-by-Side Dimension Matrix</h3>
              <p className="text-xs text-slate-500">
                Evaluation under {continuousMonths} months continuous coverage · Member age {entryAge} yrs
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {/* Filter */}
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200/80 shadow-2xs">
                <button
                  type="button"
                  onClick={() => setStatusFilter('all')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    statusFilter === 'all'
                      ? 'bg-slate-900 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  All ({result.dimensions.length})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter('gaps')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    statusFilter === 'gaps'
                      ? 'bg-amber-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Divergence ({result.dimensions.filter((d) => d.status.toLowerCase() !== 'comparable').length})
                </button>
                <button
                  type="button"
                  onClick={() => setStatusFilter('comparable')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    statusFilter === 'comparable'
                      ? 'bg-emerald-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  Parity ({result.dimensions.filter((d) => d.status.toLowerCase() === 'comparable').length})
                </button>
              </div>

              {/* View Mode Toggle */}
              <div className="flex items-center gap-1 bg-white p-1 rounded-xl border border-slate-200/80 shadow-2xs">
                <button
                  type="button"
                  onClick={() => setViewMode('cards')}
                  title="Interactive Cards View"
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    viewMode === 'cards'
                      ? 'bg-emerald-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <LayoutGrid className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Cards</span>
                </button>
                <button
                  type="button"
                  onClick={() => setViewMode('table')}
                  title="Tabular View"
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer ${
                    viewMode === 'table'
                      ? 'bg-emerald-600 text-white shadow-2xs'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  <TableIcon className="h-3.5 w-3.5" />
                  <span className="hidden sm:inline">Table</span>
                </button>
              </div>
            </div>
          </div>

          {/* VIEW MODE 1: INTERACTIVE DIMENSION CARDS */}
          {viewMode === 'cards' ? (
            <div className="space-y-4">
              {result.dimensions
                .filter((dim) => {
                  if (statusFilter === 'comparable') return dim.status.toLowerCase() === 'comparable';
                  if (statusFilter === 'gaps') return dim.status.toLowerCase() !== 'comparable';
                  return true;
                })
                .map((dim, idx) => (
                  <div
                    key={idx}
                    className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs hover:shadow-xs transition overflow-hidden"
                  >
                    {/* Dimension Title Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-2.5 bg-slate-50/80 px-4 py-3 border-b border-slate-100">
                      <div className="flex items-center gap-2">
                        <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-white border border-slate-200 text-slate-700 font-bold text-[11px] shadow-2xs">
                          {idx + 1}
                        </span>
                        <h4 className="text-sm font-bold text-slate-900">{dim.name}</h4>
                      </div>
                      <div>{getStatusBadge(dim.status)}</div>
                    </div>

                    {/* Side-by-Side Comparison Columns */}
                    <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-slate-100 p-4 gap-4 md:gap-0">
                      {/* Policy A */}
                      <div className="md:pr-5 space-y-2">
                        <div className="flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-emerald-800 uppercase tracking-wider bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200/60">
                            <FileText className="h-3 w-3 text-emerald-600" />
                            Policy A: {formatPolicyDisplayName(result.policy_a_name || policyA?.filename || policyA?.document_name, 'Baseline')}
                          </span>
                        </div>
                        <div className="pl-0.5 pt-1">
                          <PolicyValueDisplay value={dim.policy_a_value} isPolicyA={true} />
                        </div>
                      </div>

                      {/* Policy B */}
                      <div className="md:pl-5 space-y-2 pt-3 md:pt-0">
                        <div className="flex items-center justify-between">
                          <span className="inline-flex items-center gap-1.5 text-[10px] font-bold text-blue-800 uppercase tracking-wider bg-blue-50 px-2 py-0.5 rounded-md border border-blue-200/60">
                            <FileCheck2 className="h-3 w-3 text-blue-600" />
                            Policy B: {formatPolicyDisplayName(result.policy_b_name || policyB?.filename || policyB?.document_name, 'Comparison')}
                          </span>
                        </div>
                        <div className="pl-0.5 pt-1">
                          <PolicyValueDisplay value={dim.policy_b_value} isPolicyA={false} />
                        </div>
                      </div>
                    </div>

                    {/* Takeaway Assessment */}
                    <div className="px-4 pb-4">
                      {renderAssessment(
                        dim.assessment,
                        result.policy_a_name || policyA?.filename || policyA?.document_name,
                        result.policy_b_name || policyB?.filename || policyB?.document_name
                      )}
                    </div>
                  </div>
                ))}
            </div>
          ) : (
            /* VIEW MODE 2: TABULAR COMPARISON MATRIX */
            <div className="rounded-2xl border border-slate-200/90 bg-white shadow-2xs overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="bg-slate-50 text-slate-700 border-b border-slate-200">
                    <tr>
                      <th className="py-3.5 px-4 font-bold text-slate-800 w-1/4">Coverage Dimension</th>
                      <th className="py-3.5 px-4 font-bold text-emerald-900 bg-emerald-50/70 border-b border-emerald-200 w-1/4">
                        <span className="flex items-center gap-1.5">
                          <FileText className="h-3.5 w-3.5 text-emerald-600" />
                          Policy A: {formatPolicyDisplayName(result.policy_a_name || policyA?.filename || policyA?.document_name, 'Baseline')}
                        </span>
                      </th>
                      <th className="py-3.5 px-4 font-bold text-blue-900 bg-blue-50/70 border-b border-blue-200 w-1/4">
                        <span className="flex items-center gap-1.5">
                          <FileCheck2 className="h-3.5 w-3.5 text-blue-600" />
                          Policy B: {formatPolicyDisplayName(result.policy_b_name || policyB?.filename || policyB?.document_name, 'Comparison')}
                        </span>
                      </th>
                      <th className="py-3.5 px-4 font-bold text-slate-800 w-1/4">Clause Assessment</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 text-slate-700">
                    {result.dimensions
                      .filter((dim) => {
                        if (statusFilter === 'comparable') return dim.status.toLowerCase() === 'comparable';
                        if (statusFilter === 'gaps') return dim.status.toLowerCase() !== 'comparable';
                        return true;
                      })
                      .map((dim, idx) => (
                        <tr key={idx} className="hover:bg-slate-50/70 transition">
                          <td className="py-3.5 px-4 align-top">
                            <div className="space-y-1.5">
                              <p className="font-bold text-slate-900">{dim.name}</p>
                              <div>{getStatusBadge(dim.status)}</div>
                            </div>
                          </td>
                          <td className="py-3.5 px-4 align-top bg-emerald-50/20">
                            <PolicyValueDisplay value={dim.policy_a_value} isPolicyA={true} />
                          </td>
                          <td className="py-3.5 px-4 align-top bg-blue-50/20">
                            <PolicyValueDisplay value={dim.policy_b_value} isPolicyA={false} />
                          </td>
                          <td className="py-3.5 px-4 align-top">
                            {renderAssessment(
                              dim.assessment,
                              result.policy_a_name || policyA?.filename || policyA?.document_name,
                              result.policy_b_name || policyB?.filename || policyB?.document_name
                            )}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
