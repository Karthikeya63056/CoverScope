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
  FileText,
  Clock,
  ArrowRight,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, ScenarioResponse } from '../lib/types';

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
    </div>
  );
};
