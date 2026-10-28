import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  Scale,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  AlertCircle,
  Info,
  FileText,
  Clock,
  ArrowRight,
  RefreshCw,
  History,
  Calendar,
  Filter,
  X,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, ScenarioResponse, ScenarioRecord } from '../lib/types';

export const ScenarioAnalyzerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');

  // Form parameters
  const [ailment, setAilment] = useState('Type 2 Diabetes Mellitus');
  const [elapsedMonths, setElapsedMonths] = useState<number>(18);
  const [elapsedDays, setElapsedDays] = useState<number | ''>(15);
  const [memberAge, setMemberAge] = useState<number>(45);
  const [scenarioType, setScenarioType] = useState<string>('pre_existing_condition');

  const [isLoadingPolicies, setIsLoadingPolicies] = useState(true);
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [result, setResult] = useState<ScenarioResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // History State
  const [historyRecords, setHistoryRecords] = useState<ScenarioRecord[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<ScenarioRecord | null>(null);
  const [historyFilterPolicyOnly, setHistoryFilterPolicyOnly] = useState(false);

  const fetchHistory = async (policyIdFilter?: string) => {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const records = await api.getScenarioHistory(policyIdFilter);
      setHistoryRecords(records || []);
    } catch (err: any) {
      console.warn('Failed to load scenario history:', err);
      setHistoryError(err?.message || 'Failed to load scenario evaluation history.');
    } finally {
      setIsLoadingHistory(false);
    }
  };

  const handleLoadRecordIntoForm = (rec: ScenarioRecord) => {
    if (rec.input_summary) {
      if (rec.input_summary.policy_id && policies.some((p) => (p.policy_id || p.id) === rec.input_summary?.policy_id)) {
        setSelectedPolicyId(rec.input_summary.policy_id);
      }
      if (rec.input_summary.ailment) {
        setAilment(rec.input_summary.ailment);
      }
      if (rec.input_summary.elapsed_months != null) {
        setElapsedMonths(rec.input_summary.elapsed_months);
      }
      if (rec.input_summary.elapsed_days != null) {
        setElapsedDays(rec.input_summary.elapsed_days);
      }
      if (rec.input_summary.member_age != null) {
        setMemberAge(rec.input_summary.member_age);
      }
      if (rec.input_summary.scenario_type) {
        setScenarioType(rec.input_summary.scenario_type);
      }
    }
    setSelectedRecord(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const getPolicyDisplayName = (policyId: string, resultPolicyName?: string) => {
    if (resultPolicyName) return resultPolicyName;
    const match = policies.find((p) => (p.policy_id || p.id) === policyId);
    return match?.document_name || match?.filename || policyId || 'Policy Document';
  };

  useEffect(() => {
    async function loadPolicies() {
      try {
        const res = await api.listPolicies();
        setPolicies(res.policies || []);
        const paramId = searchParams.get('policy');
        const list = res.policies || [];
        if (paramId && list.some((p) => (p.policy_id || p.id) === paramId)) {
          setSelectedPolicyId(paramId);
        } else if (list.length > 0) {
          setSelectedPolicyId(list[0].policy_id || list[0].id || '');
        }
      } catch (err: any) {
        setErrorMsg('Failed to load policies.');
      } finally {
        setIsLoadingPolicies(false);
      }
    }
    loadPolicies();
  }, [searchParams]);

  useEffect(() => {
    const filterId = historyFilterPolicyOnly ? (selectedPolicyId || undefined) : undefined;
    fetchHistory(filterId);
  }, [historyFilterPolicyOnly, selectedPolicyId]);

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPolicyId || !ailment.trim()) {
      setErrorMsg('Please select a policy document and enter an ailment name.');
      return;
    }

    setIsEvaluating(true);
    setErrorMsg(null);
    setResult(null);

    try {
      const res = await api.evaluateScenario({
        policy_id: selectedPolicyId,
        ailment: ailment.trim(),
        elapsed_months: Number(elapsedMonths),
        elapsed_days: scenarioType === 'initial_waiting_period' && elapsedDays !== '' ? Number(elapsedDays) : undefined,
        member_age: Number(memberAge),
        scenario_type: scenarioType,
      });
      setResult(res);
      fetchHistory(historyFilterPolicyOnly ? selectedPolicyId : undefined);
    } catch (err: any) {
      setErrorMsg(err.message || 'Scenario evaluation failed.');
    } finally {
      setIsEvaluating(false);
    }
  };

  const getVerdictStyle = (verdict: string, currentScenarioType: string) => {
    const v = verdict.toLowerCase();
    if (currentScenarioType === 'entry_age_copayment') {
      if (v === 'waiting_period_satisfied' || v === 'covered') {
        const isNoClause = result?.headline?.toLowerCase().includes('no mandatory') || result?.calculation_formula?.includes('None found');
        return {
          bg: 'bg-emerald-50 border-emerald-200 text-emerald-900',
          badge: 'bg-emerald-600 text-white',
          icon: CheckCircle2,
          label: isNoClause ? 'No Mandatory Co-Payment Found (0% Cost-Sharing)' : 'Co-Payment Not Applicable (Age Below Threshold)',
        };
      }
      if (v === 'conditional_review' || v === 'waiting_period_active') {
        return {
          bg: 'bg-amber-50 border-amber-200 text-amber-900',
          badge: 'bg-amber-600 text-white',
          icon: Clock,
          label: 'Co-Payment Applicable (Cost-Sharing Required)',
        };
      }
    }
    if (v === 'waiting_period_satisfied' || v === 'covered') {
      return {
        bg: 'bg-emerald-50 border-emerald-200 text-emerald-900',
        badge: 'bg-emerald-600 text-white',
        icon: CheckCircle2,
        label: 'Waiting Period Satisfied',
      };
    }
    if (v === 'waiting_period_active') {
      return {
        bg: 'bg-amber-50 border-amber-200 text-amber-900',
        badge: 'bg-amber-600 text-white',
        icon: Clock,
        label: 'Waiting Period Active',
      };
    }
    if (v === 'exclusion_identified' || v === 'excluded') {
      return {
        bg: 'bg-rose-50 border-rose-200 text-rose-900',
        badge: 'bg-rose-600 text-white',
        icon: XCircle,
        label: 'Exclusion Identified',
      };
    }
    if (v === 'conditional_review') {
      return {
        bg: 'bg-blue-50 border-blue-200 text-blue-900',
        badge: 'bg-blue-600 text-white',
        icon: AlertTriangle,
        label: 'Conditional Review Required',
      };
    }
    return {
      bg: 'bg-slate-50 border-slate-200 text-slate-800',
      badge: 'bg-slate-600 text-white',
      icon: HelpCircle,
      label: v === 'unsupported_scenario' ? 'Unsupported Scenario' : 'Evidence Inconclusive',
    };
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Scenario Analyzer</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Evaluate claim eligibility and waiting periods against specific conditions, entry ages, and elapsed coverage.
        </p>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Input Parameters Card */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-xs">
        <form onSubmit={handleEvaluate} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Policy */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Target Policy Schedule
              </label>
              {policies.length > 0 ? (
                <select
                  value={selectedPolicyId}
                  onChange={(e) => setSelectedPolicyId(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white py-2 px-3 text-xs font-medium text-slate-800 focus:border-emerald-500 focus:outline-none"
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
              ) : (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-amber-900 text-xs">
                  No policy schedules loaded.{' '}
                  <Link to="/library" className="font-semibold underline text-amber-950">
                    Upload a policy schedule
                  </Link>
                </div>
              )}
            </div>

            {/* Evaluation Type */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Evaluation Type
              </label>
              <select
                value={scenarioType}
                onChange={(e) => setScenarioType(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 px-3 text-xs font-medium text-slate-800 focus:border-emerald-500 focus:outline-none"
              >
                <option value="pre_existing_condition">Pre-Existing Condition (PED)</option>
                <option value="initial_waiting_period">Initial Waiting Period</option>
                <option value="conditional_exclusion">Conditional Exclusion</option>
                <option value="entry_age_copayment">Entry-Age Co-Payment</option>
              </select>
            </div>

            {/* Condition/Ailment */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Condition / Treatment / Ailment
              </label>
              <input
                type="text"
                required
                value={ailment}
                onChange={(e) => setAilment(e.target.value)}
                placeholder="e.g. Cataract surgery, Diabetes, Hypertension, Knee Replacement"
                className="w-full rounded-lg border border-slate-300 py-2 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {/* Elapsed Months */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Continuous Policy Duration (Elapsed Months)
              </label>
              <input
                type="number"
                min={0}
                max={120}
                value={elapsedMonths}
                onChange={(e) => setElapsedMonths(parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-300 py-2 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Number of months active without break in coverage (e.g. 12 = 1 year, 24 = 2 years)
              </p>
            </div>

            {/* Elapsed Days for Initial Waiting Period */}
            {scenarioType === 'initial_waiting_period' && (
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                  Elapsed Days Since Inception (Days)
                </label>
                <input
                  type="number"
                  min={0}
                  max={365}
                  value={elapsedDays}
                  onChange={(e) => setElapsedDays(e.target.value === '' ? '' : parseInt(e.target.value) || 0)}
                  placeholder="e.g. 15 or 30"
                  className="w-full rounded-lg border border-slate-300 py-2 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
                />
                <p className="mt-1 text-[11px] text-slate-400">
                  Exact elapsed days since commencement (standard initial illness period is 30 days)
                </p>
              </div>
            )}

            {/* Member Age */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1.5">
                Member Age at Entry (Years)
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={memberAge}
                onChange={(e) => setMemberAge(parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-300 py-2 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
              />
              <p className="mt-1 text-[11px] text-slate-400">
                Determines age-related co-payments or sub-limits
              </p>
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isEvaluating || !selectedPolicyId}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isEvaluating ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Evaluating Clauses &amp; Waiting Periods...</span>
                </>
              ) : (
                <>
                  <Scale className="h-4 w-4" />
                  <span>Evaluate Scenario</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Results Section */}
      {result && (
        <div className="space-y-4">
          {(() => {
            const style = getVerdictStyle(result.verdict, scenarioType);
            const Icon = style.icon;
            return (
              <div className={`rounded-xl border p-6 shadow-xs ${style.bg}`}>
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-black/5 pb-4">
                  <div className="flex items-center gap-3">
                    <div className={`rounded-lg p-2 ${style.badge}`}>
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${style.badge}`}>
                          {style.label}
                        </span>
                        {result.decision_state && (
                          <span className="rounded-full bg-slate-200/80 px-2 py-0.5 text-[10px] font-mono text-slate-700">
                            {result.decision_state}
                          </span>
                        )}
                      </div>
                      <h2 className="text-base font-bold">{result.headline}</h2>
                    </div>
                  </div>
                </div>

                <div className="mt-4 text-xs leading-relaxed sm:text-sm">
                  {result.explanation}
                </div>

                {/* Calculation Formula */}
                {result.calculation_formula && (
                  <div className="mt-4 rounded-lg bg-white/90 border border-black/5 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                      Audited Calculation Formula
                    </p>
                    <p className="font-mono text-xs text-slate-800">
                      {result.calculation_formula}
                    </p>
                  </div>
                )}

                {/* Missing Inputs Alert */}
                {result.missing_inputs && result.missing_inputs.length > 0 && (
                  <div className="mt-3 rounded-lg bg-amber-50/90 border border-amber-200 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-amber-800 mb-1">
                      Missing Inputs Needed for Complete Determination
                    </p>
                    <ul className="list-disc list-inside space-y-0.5 text-xs text-amber-900">
                      {result.missing_inputs.map((m, idx) => (
                        <li key={idx}>{m}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* User Assumptions */}
                {result.user_assumptions && result.user_assumptions.length > 0 && (
                  <div className="mt-3 rounded-lg bg-slate-50/90 border border-slate-200 p-3">
                    <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                      User Assumptions &amp; Scope
                    </p>
                    <ul className="list-disc list-inside space-y-0.5 text-xs text-slate-700">
                      {result.user_assumptions.map((a, idx) => (
                        <li key={idx}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Evidentiary Grounding */}
                {result.evidentiary_support && (
                  <div className="mt-3 text-[11px] text-slate-500 italic">
                    Evidentiary grounding: {result.evidentiary_support}
                  </div>
                )}

                {/* Applicable Clauses */}
                {result.applicable_clauses && result.applicable_clauses.length > 0 && (
                  <div className="mt-6 pt-4 border-t border-black/5 space-y-2">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-600">
                      Applicable Policy Clauses ({result.applicable_clauses.length})
                    </p>
                    <div className="space-y-2">
                      {result.applicable_clauses.map((clause, idx) => (
                        <div
                          key={idx}
                          className="rounded-lg bg-white/80 p-3 text-xs border border-black/5"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-semibold text-emerald-800 bg-emerald-100/60 px-1.5 py-0.5 rounded text-[10px]">
                              Page {clause.page_number}
                            </span>
                            <span className="text-[10px] text-slate-500 font-mono">
                              Reference: {clause.chunk_id || 'policy clause'}
                            </span>
                          </div>
                          <p className="italic text-slate-700">&ldquo;{clause.text}&rdquo;</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Caveats */}
                {result.caveats && result.caveats.length > 0 && (
                  <div className="mt-4 pt-3 border-t border-black/5">
                    <p className="text-xs font-bold uppercase tracking-wider text-slate-600 mb-1.5">
                      Caveats &amp; Special Conditions
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-xs text-slate-700">
                      {result.caveats.map((c, idx) => (
                        <li key={idx}>{c}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            );
          })()}
        </div>
      )}
      {/* Scenario Evaluation History Section */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
              <History className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Scenario Evaluation History</h2>
              <p className="text-[11px] text-slate-500">
                Past rule-based coverage simulations and waiting period audits saved in MongoDB Atlas
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setHistoryFilterPolicyOnly(!historyFilterPolicyOnly)}
              className={`inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition ${
                historyFilterPolicyOnly
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
              title={historyFilterPolicyOnly ? 'Showing current policy only' : 'Showing all policies'}
            >
              <Filter className="h-3 w-3" />
              <span>{historyFilterPolicyOnly ? 'Current Policy Only' : 'All Policies'}</span>
            </button>

            <button
              type="button"
              onClick={() => fetchHistory(historyFilterPolicyOnly ? (selectedPolicyId || undefined) : undefined)}
              disabled={isLoadingHistory}
              className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition disabled:opacity-50"
              title="Refresh scenario history"
            >
              <RefreshCw className={`h-3 w-3 ${isLoadingHistory ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        {/* Loading State */}
        {isLoadingHistory && (
          <div className="space-y-2 py-4">
            {[1, 2, 3].map((n) => (
              <div key={n} className="h-14 w-full animate-pulse rounded-xl bg-slate-100" />
            ))}
          </div>
        )}

        {/* Error State */}
        {!isLoadingHistory && historyError && (
          <div className="flex items-center justify-between rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
              <span>{historyError}</span>
            </div>
            <button
              type="button"
              onClick={() => fetchHistory(historyFilterPolicyOnly ? (selectedPolicyId || undefined) : undefined)}
              className="rounded-lg bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-900 hover:bg-rose-200 transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty State */}
        {!isLoadingHistory && !historyError && historyRecords.length === 0 && (
          <div className="rounded-xl border border-dashed border-slate-200 py-10 text-center">
            <Clock className="mx-auto h-8 w-8 text-slate-400 mb-2" />
            <p className="text-xs font-semibold text-slate-700">No Scenario History Found</p>
            <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm mx-auto">
              {historyFilterPolicyOnly
                ? 'No evaluations recorded for this policy yet. Evaluate a scenario above to record an audit.'
                : 'You have not evaluated any scenarios yet. Simulate a scenario above to record your first audit.'}
            </p>
          </div>
        )}

        {/* History List Table */}
        {!isLoadingHistory && !historyError && historyRecords.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 border-b border-slate-200 text-slate-600 font-semibold">
                <tr>
                  <th className="py-2.5 px-3">Date &amp; Time</th>
                  <th className="py-2.5 px-3">Policy Document</th>
                  <th className="py-2.5 px-3">Scenario Type</th>
                  <th className="py-2.5 px-3">Ailment / Condition</th>
                  <th className="py-2.5 px-3">Verdict</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {historyRecords.map((rec) => {
                  const policyName = getPolicyDisplayName(rec.policy_id, rec.result_summary?.policy_name);
                  const sType = rec.input_summary?.scenario_type?.replace(/_/g, ' ') || 'pre existing condition';
                  const ailmentName = rec.input_summary?.ailment || rec.result_summary?.headline || 'Condition Query';
                  const verdict = rec.result_summary?.verdict || 'evaluated';
                  const dateStr = rec.created_at ? new Date(rec.created_at).toLocaleString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  }) : '—';

                  const isSatisfied = verdict.includes('satisfied') || verdict.includes('covered');
                  const isExcluded = verdict.includes('excluded') || verdict.includes('unsupported');

                  return (
                    <tr key={rec.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-3 text-slate-500 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="h-3 w-3 text-slate-400" />
                          <span>{dateStr}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3 font-medium text-slate-800 max-w-[180px] truncate" title={policyName}>
                        {policyName}
                      </td>
                      <td className="py-3 px-3 text-slate-600 capitalize whitespace-nowrap">
                        {sType}
                      </td>
                      <td className="py-3 px-3 font-semibold text-slate-900 max-w-[200px] truncate" title={ailmentName}>
                        {ailmentName}
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                          isSatisfied
                            ? 'bg-emerald-100 text-emerald-800'
                            : isExcluded
                            ? 'bg-rose-100 text-rose-800'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {verdict.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedRecord(rec)}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 hover:border-emerald-300 transition shadow-2xs"
                        >
                          <span>Inspect</span>
                          <ArrowRight className="h-3 w-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Historical Record Details Modal */}
      {selectedRecord && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-xl border border-slate-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700">
                    <History className="h-3 w-3" />
                    Historical Scenario Audit
                  </span>
                  <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-emerald-800">
                    {selectedRecord.result_summary?.verdict?.replace(/_/g, ' ') || 'EVALUATED'}
                  </span>
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  {selectedRecord.result_summary?.headline || selectedRecord.input_summary?.ailment || 'Scenario Assessment'}
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Policy: <span className="font-semibold text-slate-700">{getPolicyDisplayName(selectedRecord.policy_id, selectedRecord.result_summary?.policy_name)}</span> • {selectedRecord.created_at ? new Date(selectedRecord.created_at).toLocaleString('en-IN') : 'Date unavailable'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRecord(null)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="mt-4 space-y-4 text-xs">
              {/* Explanation Summary */}
              {selectedRecord.result_summary?.explanation && (
                <div className="rounded-xl bg-slate-50 p-4 border border-slate-200/70">
                  <h4 className="font-semibold text-slate-800 mb-1">Audit Evaluation Explanation</h4>
                  <p className="text-slate-600 leading-relaxed">
                    {selectedRecord.result_summary.explanation}
                  </p>
                </div>
              )}

              {/* Recorded Parameters */}
              <div className="rounded-xl border border-slate-200/80 p-4">
                <h4 className="font-semibold text-slate-800 mb-3 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-slate-500" />
                  Recorded Parameters at Evaluation
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Ailment / Condition</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.ailment || 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Scenario Type</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {selectedRecord.input_summary?.scenario_type?.replace(/_/g, ' ') || 'Pre Existing'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Elapsed Tenure</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.elapsed_months != null ? `${selectedRecord.input_summary.elapsed_months} months` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Member Age</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.member_age != null ? `${selectedRecord.input_summary.member_age} yrs` : 'Not specified'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Supporting Clauses / Citations if available */}
              {selectedRecord.source_references && selectedRecord.source_references.length > 0 && (
                <div className="rounded-xl border border-slate-200/80 p-4">
                  <h4 className="font-semibold text-slate-800 mb-2 flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
                    Citations &amp; Supporting Policy Clauses
                  </h4>
                  <div className="space-y-2">
                    {selectedRecord.source_references.map((clause, idx) => (
                      <div key={idx} className="rounded-lg bg-slate-50 p-2.5 border border-slate-100 text-slate-700">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-800 mb-1">
                          <span>Reference: {clause.chunk_id || `Clause ${idx + 1}`}</span>
                          {clause.page_number && (
                            <span className="text-[10px] text-slate-500">Page {clause.page_number}</span>
                          )}
                        </div>
                        {clause.text && (
                          <p className="text-[11px] text-slate-600 italic">
                            &ldquo;{clause.text}&rdquo;
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Informational Disclaimer Banner */}
              <div className="flex items-start gap-2 rounded-xl bg-slate-50 p-3 text-[11px] text-slate-500 border border-slate-200/60">
                <Info className="h-4 w-4 shrink-0 text-slate-400 mt-0.5" />
                <span>
                  This snapshot reflects the policy clauses and parameters recorded at the time of evaluation.
                  To run a fresh simulation with modified parameters, load these inputs into the form.
                </span>
              </div>
            </div>

            {/* Modal Actions */}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-4">
              <button
                type="button"
                onClick={() => handleLoadRecordIntoForm(selectedRecord)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-600 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-700 hover:bg-emerald-100 transition"
              >
                <Scale className="h-3.5 w-3.5" />
                <span>Load Parameters into Form</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedRecord(null)}
                className="rounded-lg bg-slate-100 px-4 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
