import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  ClipboardCheck,
  ShieldCheck,
  AlertTriangle,
  Info,
  CheckCircle2,
  Clock,
  Building2,
  User,
  IndianRupee,
  HelpCircle,
  Copy,
  Check,
  ArrowRight,
  FileText,
  Sparkles,
  RefreshCw,
  ListTodo,
  History,
  X,
  Calendar,
  AlertCircle,
  Filter,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type {
  ClaimRehearsalRequest,
  ClaimRehearsalResponse,
  ClaimRehearsalRecord,
  PolicySummary,
} from '../lib/types';

export const ClaimRehearsalPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const preselectedPolicyId = searchParams.get('policy') || '';

  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState(preselectedPolicyId);
  const [treatment, setTreatment] = useState('');
  const [expense, setExpense] = useState<string>('250000');
  const [memberAge, setMemberAge] = useState<string>('62');
  const [durationMonths, setDurationMonths] = useState<string>('18');
  const [roomCategory, setRoomCategory] = useState<string>('single_private');
  const [hospitalType, setHospitalType] = useState<string>('network_cashless');
  const [isPreExisting, setIsPreExisting] = useState<boolean>(false);
  const [isEmergency, setIsEmergency] = useState<boolean>(false);

  // Results & UI State
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ClaimRehearsalResponse | null>(null);
  const [completedChecklist, setCompletedChecklist] = useState<Record<string, boolean>>({});
  const [copiedQuestionIndex, setCopiedQuestionIndex] = useState<number | null>(null);

  // History State
  const [historyRecords, setHistoryRecords] = useState<ClaimRehearsalRecord[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [selectedRecord, setSelectedRecord] = useState<ClaimRehearsalRecord | null>(null);
  const [historyFilterPolicyOnly, setHistoryFilterPolicyOnly] = useState(false);

  const fetchHistory = async (policyIdFilter?: string) => {
    setIsLoadingHistory(true);
    setHistoryError(null);
    try {
      const records = await api.getClaimRehearsalHistory(policyIdFilter);
      setHistoryRecords(records || []);
    } catch (err: any) {
      console.warn('Failed to load claim rehearsal history:', err);
      setHistoryError(err?.message || 'Failed to load rehearsal history.');
    } finally {
      setIsLoadingHistory(false);
    }
  };

  // Load policies on mount
  useEffect(() => {
    async function loadPolicies() {
      try {
        const res = await api.listPolicies();
        setPolicies(res.policies);
        if (!selectedPolicyId && res.policies.length > 0) {
          const defaultId = res.policies[0].policy_id || res.policies[0].id || '';
          setSelectedPolicyId(defaultId);
        }
      } catch (err) {
        console.warn('Failed to load policies:', err);
      }
    }
    loadPolicies();
  }, []);

  // Fetch history when filter mode or policy changes
  useEffect(() => {
    const filterId = historyFilterPolicyOnly ? (selectedPolicyId || undefined) : undefined;
    fetchHistory(filterId);
  }, [historyFilterPolicyOnly, selectedPolicyId]);

  const handleSuggestion = (prompt: string, defaultExpense: string) => {
    setTreatment(prompt);
    if (!expense) setExpense(defaultExpense);
  };

  const handleRunRehearsal = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPolicyId) {
      setError('Please select a target policy document.');
      return;
    }
    if (!treatment.trim()) {
      setError('Please provide a medical diagnosis or treatment description.');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const payload: ClaimRehearsalRequest = {
        policy_id: selectedPolicyId,
        treatment_description: treatment.trim(),
        estimated_expense: expense ? parseFloat(expense) : null,
        member_age: memberAge ? parseInt(memberAge, 10) : null,
        policy_duration_months: durationMonths ? parseInt(durationMonths, 10) : 12,
        room_category: roomCategory,
        hospital_type: hospitalType,
        is_pre_existing: isPreExisting,
        is_emergency: isEmergency,
      };

      const res = await api.rehearseClaim(payload);
      setResult(res);

      // Initialize checklist state
      const initialCompleted: Record<string, boolean> = {};
      res.checklist.forEach((item) => {
        initialCompleted[item.id] = false;
      });
      setCompletedChecklist(initialCompleted);

      // Re-fetch history to include the new simulation
      fetchHistory(historyFilterPolicyOnly ? selectedPolicyId : undefined);
    } catch (err: any) {
      setError(err?.message || 'Failed to complete claim rehearsal.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLoadRecordIntoForm = (rec: ClaimRehearsalRecord) => {
    if (rec.input_summary) {
      if (rec.input_summary.policy_id && policies.some((p) => (p.policy_id || p.id) === rec.input_summary?.policy_id)) {
        setSelectedPolicyId(rec.input_summary.policy_id);
      }
      setTreatment(rec.input_summary.treatment_description || '');
      setExpense(rec.input_summary.estimated_expense != null ? String(rec.input_summary.estimated_expense) : '');
      setMemberAge(rec.input_summary.member_age != null ? String(rec.input_summary.member_age) : '');
      setDurationMonths(rec.input_summary.policy_duration_months != null ? String(rec.input_summary.policy_duration_months) : '12');
      setRoomCategory(rec.input_summary.room_category || 'single_private');
      setHospitalType(rec.input_summary.hospital_type || 'network_cashless');
      setIsPreExisting(!!rec.input_summary.is_pre_existing);
      setIsEmergency(!!rec.input_summary.is_emergency);
    }
    setSelectedRecord(null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const getPolicyDisplayName = (policyId: string, resultPolicyName?: string) => {
    if (resultPolicyName) return resultPolicyName;
    const match = policies.find((p) => (p.policy_id || p.id) === policyId);
    return match?.document_name || match?.filename || policyId || 'Policy Document';
  };

  const renderReadinessBadge = (status?: string) => {
    const s = (status || '').toLowerCase();
    if (s.includes('ready')) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] font-semibold text-emerald-800">
          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
          Ready to Verify
        </span>
      );
    }
    if (s.includes('check') || s.includes('important')) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
          <AlertTriangle className="h-3 w-3 text-amber-600" />
          Checks Required
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-0.5 text-[11px] font-semibold text-slate-700">
        <Info className="h-3 w-3 text-slate-500" />
        {status || 'Unknown'}
      </span>
    );
  };

  const toggleChecklistItem = (id: string) => {
    setCompletedChecklist((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const copyQuestion = (q: string, idx: number) => {
    navigator.clipboard.writeText(q);
    setCopiedQuestionIndex(idx);
    setTimeout(() => setCopiedQuestionIndex(null), 2000);
  };

  const completedCount = Object.values(completedChecklist).filter(Boolean).length;
  const totalChecklistCount = result?.checklist.length || 0;
  const checklistProgress = totalChecklistCount > 0 ? Math.round((completedCount / totalChecklistCount) * 100) : 0;

  return (
    <div className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200/80 pb-6">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-700 mb-2 border border-emerald-200">
            <ClipboardCheck className="h-3.5 w-3.5" />
            <span>Pre-Admission Simulation</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
            Claim Rehearsal
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500 max-w-2xl">
            Simulate your planned hospitalization against verified policy rules. Detect active waiting periods,
            avoid proportionate room-rent deductions, and prepare your cashless pre-authorization checklist.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Rehearsal Input Form */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
          <div className="flex items-center gap-2 mb-5 pb-3 border-b border-slate-100">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100 text-emerald-800">
              <ClipboardCheck className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Hospitalization Setup</h2>
              <p className="text-[11px] text-slate-500">Configure parameters for evidence analysis</p>
            </div>
          </div>

          <form onSubmit={handleRunRehearsal} className="space-y-4 text-xs">
            {/* Target Policy */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Target Policy Schedule <span className="text-rose-500">*</span>
              </label>
              {policies.length > 0 ? (
                <select
                  value={selectedPolicyId}
                  onChange={(e) => setSelectedPolicyId(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-slate-50/50 p-2.5 text-xs text-slate-800 focus:border-emerald-600 focus:bg-white focus:outline-hidden"
                >
                  {policies.map((p) => {
                    const id = p.policy_id || p.id || '';
                    const name = p.filename || p.document_name || 'Policy Document';
                    return (
                      <option key={id} value={id}>
                        {name} ({p.page_count} pages)
                      </option>
                    );
                  })}
                </select>
              ) : (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-amber-900 text-xs">
                  No policy schedules loaded.{' '}
                  <Link to="/library" className="font-semibold underline">
                    Upload a policy schedule
                  </Link>
                </div>
              )}
            </div>

            {/* Treatment Description */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Planned Treatment or Diagnosis <span className="text-rose-500">*</span>
              </label>
              <input
                type="text"
                value={treatment}
                onChange={(e) => setTreatment(e.target.value)}
                placeholder="e.g. Total Knee Replacement, Cataract Surgery, Day Care"
                className="w-full rounded-lg border border-slate-200 bg-white p-2.5 text-xs text-slate-900 placeholder:text-slate-400 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
              />

              {/* Quick Preset Suggestion Pills */}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {[
                  { label: 'Knee Surgery', full: 'Total Knee Replacement Surgery', expense: '300000' },
                  { label: 'Cataract', full: 'Cataract Surgery in Right Eye', expense: '45000' },
                  { label: 'Gallbladder', full: 'Laparoscopic Cholecystectomy (Gallbladder)', expense: '110000' },
                  { label: 'Maternity', full: 'Maternity Normal Delivery', expense: '60000' },
                ].map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => handleSuggestion(preset.full, preset.expense)}
                    className="rounded-md border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-medium text-slate-600 hover:bg-slate-100 hover:text-slate-900 transition"
                  >
                    + {preset.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Financial Estimates */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Estimated Bill (₹)
                </label>
                <div className="relative">
                  <span className="absolute inset-y-0 left-0 flex items-center pl-2.5 text-slate-400 font-semibold">₹</span>
                  <input
                    type="number"
                    value={expense}
                    onChange={(e) => setExpense(e.target.value)}
                    placeholder="250000"
                    min="0"
                    className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-7 pr-2.5 text-xs text-slate-900 focus:border-emerald-600 focus:outline-hidden"
                  />
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Member Age at Entry
                </label>
                <input
                  type="number"
                  value={memberAge}
                  onChange={(e) => setMemberAge(e.target.value)}
                  placeholder="e.g. 62"
                  min="0"
                  max="120"
                  className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-900 focus:border-emerald-600 focus:outline-hidden"
                />
              </div>
            </div>

            {/* Policy Duration & Hospital Category */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Continuous Duration
                </label>
                <div className="relative">
                  <input
                    type="number"
                    value={durationMonths}
                    onChange={(e) => setDurationMonths(e.target.value)}
                    placeholder="18"
                    min="0"
                    className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-2.5 pr-14 text-xs text-slate-900 focus:border-emerald-600 focus:outline-hidden"
                  />
                  <span className="absolute inset-y-0 right-0 flex items-center pr-2 text-[10px] text-slate-400 font-medium">
                    months
                  </span>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-700 mb-1">
                  Admission Channel
                </label>
                <select
                  value={hospitalType}
                  onChange={(e) => setHospitalType(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 bg-white p-2 text-xs text-slate-800 focus:border-emerald-600 focus:outline-hidden"
                >
                  <option value="network_cashless">Cashless Network</option>
                  <option value="non_network_reimbursement">Reimbursement (Non-Network)</option>
                </select>
              </div>
            </div>

            {/* Room Category */}
            <div>
              <label className="block font-semibold text-slate-700 mb-1">
                Room Category Planned
              </label>
              <select
                value={roomCategory}
                onChange={(e) => setRoomCategory(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white p-2.5 text-xs text-slate-800 focus:border-emerald-600 focus:outline-hidden"
              >
                <option value="single_private">Single Private A/C Room (Standard Entitlement)</option>
                <option value="shared">Twin Sharing / Semi-Private</option>
                <option value="deluxe_suite">Deluxe Suite / Luxury Room (⚠️ Surcharges apply)</option>
                <option value="icu">ICU / Intensive Care Unit</option>
                <option value="general">General Ward</option>
              </select>
            </div>

            {/* Toggles */}
            <div className="space-y-2 pt-1 border-t border-slate-100">
              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={isPreExisting}
                  onChange={(e) => setIsPreExisting(e.target.checked)}
                  className="h-4 w-4 rounded-sm border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-slate-700 font-medium">
                  Pre-existing condition (diagnosed prior to policy inception)
                </span>
              </label>

              <label className="flex items-center gap-2 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={isEmergency}
                  onChange={(e) => setIsEmergency(e.target.checked)}
                  className="h-4 w-4 rounded-sm border-slate-300 text-emerald-600 focus:ring-emerald-500"
                />
                <span className="text-slate-700 font-medium">
                  Emergency hospitalization / Accidental injury
                </span>
              </label>
            </div>

            {error && (
              <div className="rounded-lg border border-rose-200 bg-rose-50 p-2.5 text-rose-700 text-xs">
                {error}
              </div>
            )}

            {/* Run Button */}
            <button
              type="submit"
              disabled={isLoading || policies.length === 0}
              className="w-full flex items-center justify-center gap-2 rounded-lg bg-emerald-600 py-3 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isLoading ? (
                <>
                  <RefreshCw className="h-4 w-4 animate-spin" />
                  <span>Evaluating Policy Grounding...</span>
                </>
              ) : (
                <>
                  <ClipboardCheck className="h-4 w-4" />
                  <span>Run Claim Rehearsal</span>
                </>
              )}
            </button>
          </form>
        </div>

        {/* Right Column: Rehearsal Report Output */}
        <div className="lg:col-span-7 space-y-6">
          {result ? (
            <div className="space-y-6">
              {/* Readiness Banner */}
              <div
                className={`rounded-2xl border p-6 shadow-xs ${
                  result.readiness_status === 'ready_to_verify'
                    ? 'border-emerald-200 bg-emerald-50/60 text-emerald-950'
                    : result.readiness_status === 'important_checks_required'
                    ? 'border-amber-200 bg-amber-50/70 text-amber-950'
                    : 'border-slate-200 bg-slate-50 text-slate-900'
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                          result.readiness_status === 'ready_to_verify'
                            ? 'bg-emerald-600 text-white'
                            : result.readiness_status === 'important_checks_required'
                            ? 'bg-amber-600 text-white'
                            : 'bg-slate-700 text-white'
                        }`}
                      >
                        {result.readiness_status === 'ready_to_verify'
                          ? 'Ready to Verify'
                          : result.readiness_status === 'important_checks_required'
                          ? 'Important Checks Required'
                          : 'Insufficient Information'}
                      </span>
                      <span className="text-xs text-slate-500 font-medium">
                        Target: {result.policy_name}
                      </span>
                    </div>
                    <h2 className="text-lg font-bold text-slate-900 pt-1">
                      {result.headline}
                    </h2>
                    <p className="text-xs text-slate-700 leading-relaxed pt-1">
                      {result.executive_summary}
                    </p>
                  </div>
                </div>
              </div>

              {/* Missing Information Callout */}
              {result.missing_information && result.missing_information.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 space-y-1.5 text-xs text-amber-900 shadow-xs">
                  <div className="flex items-center gap-2 font-bold text-amber-950">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Inputs Required for Complete Verification</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 pl-1 text-[11px] text-amber-900">
                    {result.missing_information.map((item, mIdx) => (
                      <li key={mIdx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Unresolved Assumptions Callout */}
              {result.unresolved_assumptions && result.unresolved_assumptions.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50/90 p-4 space-y-1.5 text-xs text-slate-800 shadow-xs">
                  <div className="flex items-center gap-2 font-bold text-slate-900">
                    <HelpCircle className="h-4 w-4 text-slate-600" />
                    <span>Simulation Default Assumptions</span>
                  </div>
                  <ul className="list-disc list-inside space-y-1 pl-1 text-[11px] text-slate-600">
                    {result.unresolved_assumptions.map((item, aIdx) => (
                      <li key={aIdx}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Financial Exposure Card (if calculated) */}
              {result.financial_breakdown && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
                        <IndianRupee className="h-4 w-4" />
                      </div>
                      <h3 className="text-sm font-bold text-slate-900">
                        Financial Exposure &amp; Liability Estimate
                      </h3>
                    </div>
                    <span className="text-[10px] font-medium text-slate-400">
                      Based on policy terms
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-center">
                    <div className="rounded-xl bg-slate-50 p-3 border border-slate-100">
                      <p className="text-[11px] font-semibold text-slate-500 uppercase">Estimated Bill</p>
                      <p className="mt-1 text-lg font-bold text-slate-900">
                        ₹{result.financial_breakdown.estimated_bill?.toLocaleString() || '0'}
                      </p>
                    </div>

                    <div className="rounded-xl bg-emerald-50 p-3 border border-emerald-100">
                      <p className="text-[11px] font-semibold text-emerald-700 uppercase">Insurer Coverage</p>
                      <p className="mt-1 text-lg font-bold text-emerald-700">
                        ₹{result.financial_breakdown.estimated_insurer_coverage?.toLocaleString() || '0'}
                      </p>
                    </div>

                    <div className="rounded-xl bg-rose-50 p-3 border border-rose-100">
                      <p className="text-[11px] font-semibold text-rose-700 uppercase">Estimated Out-of-Pocket</p>
                      <p className="mt-1 text-lg font-bold text-rose-700">
                        ₹{result.financial_breakdown.estimated_out_of_pocket?.toLocaleString() || '0'}
                      </p>
                    </div>
                  </div>

                  {result.financial_breakdown.calculation_notes.length > 0 && (
                    <div className="rounded-lg bg-slate-50/70 p-3 text-xs text-slate-600 space-y-1 border border-slate-100">
                      <p className="font-semibold text-slate-700">Deduction Details:</p>
                      <ul className="list-disc list-inside space-y-0.5 text-[11px]">
                        {result.financial_breakdown.calculation_notes.map((note, nIdx) => (
                          <li key={nIdx}>{note}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-400 italic">
                    Disclaimer: Calculations are deterministic estimations based on extracted policy terms and user inputs; not a guarantee of claim settlement by the insurer.
                  </p>
                </div>
              )}

              {/* Relevant Policy Conditions & Rules */}
              {result.relevant_conditions.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                      <ShieldCheck className="h-4 w-4" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Applicable Policy Conditions &amp; Restrictions
                    </h3>
                  </div>

                  <div className="space-y-3">
                    {result.relevant_conditions.map((cond, cIdx) => (
                      <div
                        key={cIdx}
                        className="rounded-xl border border-slate-100 bg-slate-50/50 p-3.5 space-y-1 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-bold text-slate-800">{cond.title}</span>
                          <span
                            className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider ${
                              cond.severity === 'high'
                                ? 'bg-rose-100 text-rose-800'
                                : cond.severity === 'medium'
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {cond.category}
                          </span>
                        </div>
                        <p className="text-slate-600 leading-relaxed text-[11px]">
                          {cond.details}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Supporting Verbatim Clauses */}
              {result.supporting_clauses.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                      <FileText className="h-4 w-4" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Supporting Verbatim Policy Clauses ({result.supporting_clauses.length})
                    </h3>
                  </div>

                  <div className="space-y-2.5">
                    {result.supporting_clauses.map((clause, clIdx) => (
                      <div
                        key={clIdx}
                        className="rounded-xl border border-slate-200/80 bg-slate-50/30 p-3.5 space-y-1.5 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="rounded-md bg-emerald-100/70 text-emerald-800 px-2 py-0.5 text-[10px] font-bold">
                            Page {clause.page_number} ({clause.chunk_id})
                          </span>
                          {clause.topic && (
                            <span className="text-[10px] font-semibold text-slate-500">
                              {clause.topic}
                            </span>
                          )}
                        </div>
                        <p className="italic text-slate-700 leading-relaxed text-[11px] border-l-2 border-emerald-500 pl-2.5">
                          &ldquo;{clause.quote}&rdquo;
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pre-Admission Preparation Checklist */}
              {result.checklist.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-purple-50 text-purple-700">
                        <ListTodo className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Pre-Admission Claim Preparation Checklist
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          {completedCount} of {totalChecklistCount} tasks completed ({checklistProgress}%)
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="h-1.5 w-full rounded-full bg-slate-100 overflow-hidden">
                    <div
                      className="h-full bg-emerald-600 transition-all duration-300 rounded-full"
                      style={{ width: `${checklistProgress}%` }}
                    />
                  </div>

                  <div className="space-y-2.5">
                    {result.checklist.map((item) => {
                      const isChecked = !!completedChecklist[item.id];
                      return (
                        <div
                          key={item.id}
                          onClick={() => toggleChecklistItem(item.id)}
                          className={`rounded-xl border p-3 text-xs transition cursor-pointer flex items-start gap-3 ${
                            isChecked
                              ? 'border-emerald-200 bg-emerald-50/40 text-slate-600'
                              : 'border-slate-200 bg-white hover:border-slate-300'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}}
                            className="mt-0.5 h-4 w-4 rounded-sm border-slate-300 text-emerald-600 focus:ring-emerald-500 shrink-0"
                          />
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span
                                className={`font-semibold ${
                                  isChecked ? 'line-through text-slate-500' : 'text-slate-900'
                                }`}
                              >
                                {item.title}
                              </span>
                              {item.is_mandatory && (
                                <span className="rounded-full bg-rose-50 px-1.5 py-0.2 text-[9px] font-bold text-rose-700">
                                  Mandatory
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] text-slate-600 leading-relaxed">
                              {item.description}
                            </p>
                            <p className="text-[10px] text-emerald-700 font-medium">
                              💡 Action: {item.suggested_action}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Questions to Ask Insurer or TPA Desk */}
              {result.questions_to_ask_tpa.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-3">
                  <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
                    <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                      <HelpCircle className="h-4 w-4" />
                    </div>
                    <h3 className="text-sm font-bold text-slate-900">
                      Questions to Ask Your Insurer or Hospital TPA Desk
                    </h3>
                  </div>

                  <div className="space-y-2">
                    {result.questions_to_ask_tpa.map((question, qIdx) => (
                      <div
                        key={qIdx}
                        className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 bg-slate-50/70 p-3 text-xs text-slate-800"
                      >
                        <span className="font-medium text-[11px]">{question}</span>
                        <button
                          type="button"
                          onClick={() => copyQuestion(question, qIdx)}
                          className="flex items-center gap-1 rounded-md border border-slate-200 bg-white px-2 py-1 text-[10px] font-semibold text-slate-600 hover:bg-slate-50 shrink-0"
                          title="Copy question text"
                        >
                          {copiedQuestionIndex === qIdx ? (
                            <>
                              <Check className="h-3 w-3 text-emerald-600" />
                              <span className="text-emerald-600">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3 w-3" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Empty State */
            <div className="rounded-2xl border border-dashed border-slate-200 bg-white p-12 text-center shadow-xs">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600 mb-3">
                <ClipboardCheck className="h-6 w-6" />
              </div>
              <h3 className="text-base font-bold text-slate-900">No Rehearsal Run Yet</h3>
              <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto leading-relaxed">
                Fill in the hospitalization parameters on the left and click &ldquo;Run Claim Rehearsal&rdquo; to simulate
                your claim eligibility, financial exposure, and pre-admission requirements.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] text-slate-600">
                  ⚡ Zero Hallucinations
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] text-slate-600">
                  📄 Verbatim Policy Citations
                </span>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-[11px] text-slate-600">
                  💰 Co-pay &amp; Rent Estimator
                </span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Rehearsal History Section */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4 mb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
              <History className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-900">Rehearsal History &amp; Audit Records</h2>
              <p className="text-[11px] text-slate-500">
                Past claim simulations and readiness assessments saved in MongoDB Atlas
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
              title="Refresh rehearsal history"
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
            <p className="text-xs font-semibold text-slate-700">No Rehearsal History Found</p>
            <p className="text-[11px] text-slate-400 mt-0.5 max-w-sm mx-auto">
              {historyFilterPolicyOnly
                ? 'No simulations recorded for this policy yet. Run a rehearsal above to record an audit record.'
                : 'You have not run any claim rehearsals yet. Simulate a claim above to record your first audit.'}
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
                  <th className="py-2.5 px-3">Planned Treatment</th>
                  <th className="py-2.5 px-3">Estimated Bill</th>
                  <th className="py-2.5 px-3">Readiness Status</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700">
                {historyRecords.map((rec) => {
                  const policyName = getPolicyDisplayName(rec.policy_id, rec.result_summary?.policy_name);
                  const treatmentDesc = rec.input_summary?.treatment_description || rec.result_summary?.headline || 'Hospitalization Consultation';
                  const exp = rec.input_summary?.estimated_expense != null
                    ? `₹${Number(rec.input_summary.estimated_expense).toLocaleString('en-IN')}`
                    : '—';
                  const dateStr = rec.created_at ? new Date(rec.created_at).toLocaleString('en-IN', {
                    day: 'numeric',
                    month: 'short',
                    year: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                  }) : '—';

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
                      <td className="py-3 px-3 font-semibold text-slate-900 max-w-[200px] truncate" title={treatmentDesc}>
                        {treatmentDesc}
                      </td>
                      <td className="py-3 px-3 text-slate-700 whitespace-nowrap">
                        {exp}
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap">
                        {renderReadinessBadge(rec.result_summary?.readiness_status)}
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
                    Historical Audit Record
                  </span>
                  {renderReadinessBadge(selectedRecord.result_summary?.readiness_status)}
                </div>
                <h3 className="text-base font-bold text-slate-900">
                  {selectedRecord.result_summary?.headline || selectedRecord.input_summary?.treatment_description || 'Claim Rehearsal Audit'}
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
              {/* Executive Summary */}
              {selectedRecord.result_summary?.executive_summary && (
                <div className="rounded-xl bg-slate-50 p-4 border border-slate-200/70">
                  <h4 className="font-semibold text-slate-800 mb-1">Audit Assessment Summary</h4>
                  <p className="text-slate-600 leading-relaxed">
                    {selectedRecord.result_summary.executive_summary}
                  </p>
                </div>
              )}

              {/* Recorded Hospitalization Parameters */}
              <div className="rounded-xl border border-slate-200/80 p-4">
                <h4 className="font-semibold text-slate-800 mb-3 flex items-center gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-slate-500" />
                  Recorded Parameters at Evaluation
                </h4>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Estimated Bill</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.estimated_expense ? `₹${Number(selectedRecord.input_summary.estimated_expense).toLocaleString('en-IN')}` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Member Age</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.member_age ? `${selectedRecord.input_summary.member_age} yrs` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Policy Tenure</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.policy_duration_months ? `${selectedRecord.input_summary.policy_duration_months} mos` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Room Category</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {selectedRecord.input_summary?.room_category?.replace(/_/g, ' ') || 'Single Private'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Hospital Type</span>
                    <span className="font-semibold text-slate-800 capitalize">
                      {selectedRecord.input_summary?.hospital_type?.replace(/_/g, ' ') || 'Network Cashless'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Pre-Existing Condition</span>
                    <span className={`font-semibold ${selectedRecord.input_summary?.is_pre_existing ? 'text-amber-700' : 'text-slate-800'}`}>
                      {selectedRecord.input_summary?.is_pre_existing ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg">
                    <span className="block text-[10px] text-slate-400 font-medium">Emergency Admission</span>
                    <span className="font-semibold text-slate-800">
                      {selectedRecord.input_summary?.is_emergency ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Financial Snapshot if available */}
              {selectedRecord.result_summary?.financial_breakdown && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
                  <h4 className="font-semibold text-emerald-900 mb-2 flex items-center gap-1.5">
                    <IndianRupee className="h-3.5 w-3.5 text-emerald-700" />
                    Recorded Financial Breakdown
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {selectedRecord.result_summary.financial_breakdown.estimated_bill != null && (
                      <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] text-slate-500">Total Billed</span>
                        <span className="font-bold text-slate-900">₹{Number(selectedRecord.result_summary.financial_breakdown.estimated_bill).toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    {selectedRecord.result_summary.financial_breakdown.deductible_or_copay_amount != null && (
                      <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] text-slate-500">Deductible / Co-pay</span>
                        <span className="font-bold text-rose-700">₹{Number(selectedRecord.result_summary.financial_breakdown.deductible_or_copay_amount).toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    {selectedRecord.result_summary.financial_breakdown.copayment_percentage != null && (
                      <div className="bg-white/80 p-2.5 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] text-slate-500">Co-pay %</span>
                        <span className="font-bold text-amber-700">{selectedRecord.result_summary.financial_breakdown.copayment_percentage}%</span>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Supporting References if available */}
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
                          <span>{clause.topic || `Clause ${clause.chunk_id || idx + 1}`}</span>
                          {clause.page_number && (
                            <span className="text-[10px] text-slate-500">Page {clause.page_number}</span>
                          )}
                        </div>
                        {clause.quote && (
                          <p className="text-[11px] text-slate-600 italic">
                            &ldquo;{clause.quote}&rdquo;
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
                  This snapshot reflects the policy rules and parameters recorded at the time of evaluation.
                  To run a fresh simulation with updated hospital quotes or policy terms, load these parameters into the form.
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
                <ClipboardCheck className="h-3.5 w-3.5" />
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
