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
  Stethoscope,
  ChevronRight,
  ShieldAlert,
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
        setPolicies(res.policies || []);
        if (!selectedPolicyId && res.policies && res.policies.length > 0) {
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
      if (res.checklist) {
        res.checklist.forEach((item) => {
          initialCompleted[item.id] = false;
        });
      }
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
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100/80 px-2.5 py-0.5 text-[11px] font-bold text-emerald-800 border border-emerald-200">
          <CheckCircle2 className="h-3 w-3 text-emerald-600" />
          Ready to Verify
        </span>
      );
    }
    if (s.includes('check') || s.includes('important')) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100/80 px-2.5 py-0.5 text-[11px] font-bold text-amber-900 border border-amber-200">
          <AlertTriangle className="h-3 w-3 text-amber-600" />
          Checks Required
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-0.5 text-[11px] font-semibold text-slate-700 border border-slate-200">
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
  const totalChecklistCount = result?.checklist?.length || 0;
  const checklistProgress = totalChecklistCount > 0 ? Math.round((completedCount / totalChecklistCount) * 100) : 0;

  // Financial percentages for visualizer
  const billVal = result?.financial_breakdown?.estimated_bill || 0;
  const insVal = result?.financial_breakdown?.estimated_insurer_coverage || 0;
  const oopVal = result?.financial_breakdown?.estimated_out_of_pocket || 0;
  const insPct = billVal > 0 ? Math.min(100, Math.round((insVal / billVal) * 100)) : 0;
  const oopPct = billVal > 0 ? Math.min(100, 100 - insPct) : 0;

  return (
    <div className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200/80 pb-6">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200/80 px-3 py-1 text-xs font-semibold text-emerald-800">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
            </span>
            <span>Deterministic Rule Grounding Active</span>
            <span className="text-emerald-300">•</span>
            <span className="text-emerald-700/80 font-normal">Pre-Admission Simulation</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Claim Rehearsal
          </h1>
          <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
            Stress-test planned hospitalizations against verbatim policy clauses, active waiting periods, room-rent limits, and co-payment obligations before submitting pre-authorization.
          </p>
        </div>

        {/* Quick Stat Pill Group */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-200/80 bg-white px-3 py-1.5 text-slate-700 shadow-2xs font-medium">
            <ShieldCheck className="h-4 w-4 text-emerald-600" />
            <span>IRDAI Rules Grounded</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-lg border border-slate-200/80 bg-white px-3 py-1.5 text-slate-700 shadow-2xs font-medium">
            <FileText className="h-4 w-4 text-blue-600" />
            <span>Verbatim Citations</span>
          </div>
        </div>
      </div>

      {/* Main 2-Column Content Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Hospitalization Setup Form (Sticky on Desktop) */}
        <div className="lg:col-span-5 lg:sticky lg:top-20 space-y-4">
          <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100">
              <div className="flex items-center gap-2.5">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-2xs">
                  <ClipboardCheck className="h-4 w-4" />
                </div>
                <div>
                  <h2 className="text-sm font-bold text-slate-900">Hospitalization Setup</h2>
                  <p className="text-[11px] text-slate-500">Configure parameters for evidence analysis</p>
                </div>
              </div>
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-600">
                5 Engines Active
              </span>
            </div>

            <form onSubmit={handleRunRehearsal} className="space-y-4 pt-4 text-xs">
              {/* Target Policy */}
              <div className="space-y-1.5">
                <label htmlFor="target-policy-select" className="block text-xs font-semibold text-slate-800">
                  Target Policy Schedule <span className="text-rose-500">*</span>
                </label>
                {policies.length > 0 ? (
                  <select
                    id="target-policy-select"
                    value={selectedPolicyId}
                    onChange={(e) => setSelectedPolicyId(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-slate-50/70 py-2.5 px-3 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
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
                  <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-900">
                    No policy schedules loaded.{' '}
                    <Link to="/library" className="font-bold underline text-emerald-700">
                      Upload a policy document
                    </Link>
                  </div>
                )}
              </div>

              {/* Treatment Description */}
              <div className="space-y-1.5">
                <label htmlFor="treatment-input" className="block text-xs font-semibold text-slate-800">
                  Planned Treatment or Diagnosis <span className="text-rose-500">*</span>
                </label>
                <input
                  id="treatment-input"
                  type="text"
                  value={treatment}
                  onChange={(e) => setTreatment(e.target.value)}
                  placeholder="e.g. Total Knee Replacement, Cataract Surgery, Day Care"
                  className="w-full rounded-xl border border-slate-200 bg-white py-2.5 px-3 text-xs font-medium text-slate-900 placeholder:text-slate-400 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                />

                {/* Quick Clinical Scenarios Grid */}
                <div className="pt-1.5">
                  <span className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
                    Quick Clinical Presets
                  </span>
                  <div className="grid grid-cols-2 gap-1.5">
                    {[
                      { label: 'Knee Replacement', full: 'Total Knee Replacement Surgery', expense: '300000', tag: '₹3L' },
                      { label: 'Cataract Surgery', full: 'Cataract Surgery in Right Eye', expense: '45000', tag: '₹45k' },
                      { label: 'Gallbladder (Lap)', full: 'Laparoscopic Cholecystectomy (Gallbladder)', expense: '110000', tag: '₹1.1L' },
                      { label: 'Normal Delivery', full: 'Maternity Normal Delivery', expense: '60000', tag: '₹60k' },
                    ].map((preset, idx) => (
                      <button
                        key={idx}
                        type="button"
                        onClick={() => handleSuggestion(preset.full, preset.expense)}
                        className="flex items-center justify-between rounded-lg border border-slate-200/90 bg-slate-50/80 px-2.5 py-1.5 text-[11px] font-medium text-slate-700 hover:border-emerald-500 hover:bg-emerald-50/40 hover:text-emerald-900 transition-all text-left shadow-2xs"
                      >
                        <span className="truncate pr-1">+ {preset.label}</span>
                        <span className="rounded bg-white px-1.5 py-0.5 text-[9px] font-bold text-slate-500 border border-slate-200/60 shrink-0">
                          {preset.tag}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Financial Estimates (2 Columns) */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="expense-input" className="block text-xs font-semibold text-slate-800">
                    Estimated Bill (₹)
                  </label>
                  <div className="relative">
                    <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400 font-semibold text-xs pointer-events-none">
                      ₹
                    </span>
                    <input
                      id="expense-input"
                      type="number"
                      value={expense}
                      onChange={(e) => setExpense(e.target.value)}
                      placeholder="250000"
                      min="0"
                      className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-7 pr-3 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                    />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="age-input" className="block text-xs font-semibold text-slate-800">
                    Member Age at Entry
                  </label>
                  <div className="relative">
                    <input
                      id="age-input"
                      type="number"
                      value={memberAge}
                      onChange={(e) => setMemberAge(e.target.value)}
                      placeholder="62"
                      min="0"
                      max="120"
                      className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-3 pr-10 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                    />
                    <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-[11px] text-slate-400 font-medium pointer-events-none">
                      yrs
                    </span>
                  </div>
                </div>
              </div>

              {/* Duration & Admission Channel (2 Columns) */}
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label htmlFor="duration-input" className="block text-xs font-semibold text-slate-800">
                    Continuous Tenure
                  </label>
                  <div className="relative">
                    <input
                      id="duration-input"
                      type="number"
                      value={durationMonths}
                      onChange={(e) => setDurationMonths(e.target.value)}
                      placeholder="18"
                      min="0"
                      className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-3 pr-14 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                    />
                    <span className="absolute inset-y-0 right-0 flex items-center pr-3 text-[10px] text-slate-400 font-medium pointer-events-none">
                      months
                    </span>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label htmlFor="channel-select" className="block text-xs font-semibold text-slate-800">
                    Admission Channel
                  </label>
                  <select
                    id="channel-select"
                    value={hospitalType}
                    onChange={(e) => setHospitalType(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 bg-white py-2.5 px-3 text-xs font-medium text-slate-900 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
                  >
                    <option value="network_cashless">Cashless Network</option>
                    <option value="non_network_reimbursement">Reimbursement (Non-Network)</option>
                  </select>
                </div>
              </div>

              {/* Room Category Planned */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label htmlFor="room-category-select" className="block text-xs font-semibold text-slate-800">
                    Room Category Planned
                  </label>
                  {roomCategory === 'deluxe_suite' && (
                    <span className="text-[10px] font-bold text-amber-700 animate-pulse">
                      ⚠️ Proportionate deduction risk
                    </span>
                  )}
                </div>
                <select
                  id="room-category-select"
                  value={roomCategory}
                  onChange={(e) => setRoomCategory(e.target.value)}
                  className={`w-full rounded-xl border py-2.5 px-3 text-xs font-medium transition focus:outline-hidden focus:ring-1 ${
                    roomCategory === 'deluxe_suite'
                      ? 'border-amber-300 bg-amber-50/40 text-amber-950 focus:border-amber-500 focus:ring-amber-500'
                      : 'border-slate-200 bg-white text-slate-900 hover:border-slate-300 focus:border-emerald-600 focus:ring-emerald-600'
                  }`}
                >
                  <option value="single_private">Single Private A/C Room (Standard Entitlement)</option>
                  <option value="shared">Twin Sharing / Semi-Private</option>
                  <option value="deluxe_suite">Deluxe Suite / Luxury Room (⚠️ Surcharges apply)</option>
                  <option value="icu">ICU / Intensive Care Unit</option>
                  <option value="general">General Ward</option>
                </select>
              </div>

              {/* Clinical Modifiers as Segmented Toggle Cards */}
              <div className="space-y-2 pt-2 border-t border-slate-100">
                <span className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                  Clinical Modifiers
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setIsPreExisting(!isPreExisting)}
                    className={`flex items-start gap-2.5 rounded-xl border p-2.5 text-left transition-all ${
                      isPreExisting
                        ? 'border-amber-300 bg-amber-50/60 text-amber-950 shadow-2xs'
                        : 'border-slate-200/90 bg-slate-50/50 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div
                      className={`flex h-4 w-4 shrink-0 mt-0.5 items-center justify-center rounded border transition-colors ${
                        isPreExisting
                          ? 'border-amber-600 bg-amber-600 text-white'
                          : 'border-slate-300 bg-white'
                      }`}
                    >
                      {isPreExisting && <Check className="h-3 w-3 stroke-[3]" />}
                    </div>
                    <div className="text-[11px] leading-tight">
                      <span className="font-semibold block text-slate-900">Pre-Existing Condition</span>
                      <span className="text-[10px] text-slate-500">Diagnosed before inception</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => setIsEmergency(!isEmergency)}
                    className={`flex items-start gap-2.5 rounded-xl border p-2.5 text-left transition-all ${
                      isEmergency
                        ? 'border-blue-300 bg-blue-50/60 text-blue-950 shadow-2xs'
                        : 'border-slate-200/90 bg-slate-50/50 text-slate-700 hover:border-slate-300 hover:bg-slate-50'
                    }`}
                  >
                    <div
                      className={`flex h-4 w-4 shrink-0 mt-0.5 items-center justify-center rounded border transition-colors ${
                        isEmergency
                          ? 'border-blue-600 bg-blue-600 text-white'
                          : 'border-slate-300 bg-white'
                      }`}
                    >
                      {isEmergency && <Check className="h-3 w-3 stroke-[3]" />}
                    </div>
                    <div className="text-[11px] leading-tight">
                      <span className="font-semibold block text-slate-900">Emergency / Trauma</span>
                      <span className="text-[10px] text-slate-500">Waives 30-day initial waiting</span>
                    </div>
                  </button>
                </div>
              </div>

              {error && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-rose-800 text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
                  <span>{error}</span>
                </div>
              )}

              {/* Primary Run Button */}
              <button
                type="submit"
                disabled={isLoading || policies.length === 0}
                className="w-full flex items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 px-4 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 hover:shadow-md disabled:opacity-50 transition-all cursor-pointer"
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
                    <ArrowRight className="h-3.5 w-3.5 ml-0.5" />
                  </>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Right Column: Simulation Report & Grounded Evidence */}
        <div className="lg:col-span-7 space-y-6">
          {result ? (
            <div className="space-y-6">
              {/* Readiness Banner */}
              <div
                className={`rounded-2xl border p-6 shadow-xs transition-all ${
                  result.readiness_status === 'ready_to_verify'
                    ? 'border-emerald-200 bg-emerald-50/60 text-emerald-950'
                    : result.readiness_status === 'important_checks_required'
                    ? 'border-amber-200 bg-amber-50/70 text-amber-950'
                    : 'border-slate-200 bg-slate-50 text-slate-900'
                }`}
              >
                <div className="space-y-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-black/5 pb-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-wider shadow-2xs ${
                          result.readiness_status === 'ready_to_verify'
                            ? 'bg-emerald-600 text-white'
                            : result.readiness_status === 'important_checks_required'
                            ? 'bg-amber-600 text-white'
                            : 'bg-slate-700 text-white'
                        }`}
                      >
                        {result.readiness_status === 'ready_to_verify' ? (
                          <>
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            <span>Ready to Verify</span>
                          </>
                        ) : result.readiness_status === 'important_checks_required' ? (
                          <>
                            <AlertTriangle className="h-3.5 w-3.5" />
                            <span>Important Checks Required</span>
                          </>
                        ) : (
                          <>
                            <Info className="h-3.5 w-3.5" />
                            <span>Insufficient Information</span>
                          </>
                        )}
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-white/70 px-2.5 py-1 rounded-lg border border-slate-200/60 font-medium">
                      <FileText className="h-3.5 w-3.5 text-slate-500" />
                      <span className="truncate max-w-[240px]" title={result.policy_name}>
                        {result.policy_name}
                      </span>
                    </div>
                  </div>

                  <h2 className="text-lg sm:text-xl font-bold text-slate-900 pt-1 leading-snug">
                    {result.headline}
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-700 leading-relaxed">
                    {result.executive_summary}
                  </p>
                </div>
              </div>

              {/* Missing Information Callout */}
              {result.missing_information && result.missing_information.length > 0 && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 space-y-2 text-xs text-amber-900 shadow-xs">
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
                <div className="rounded-xl border border-slate-200 bg-slate-50/90 p-4 space-y-2 text-xs text-slate-800 shadow-xs">
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

              {/* Financial Exposure & Liability Breakdown */}
              {result.financial_breakdown && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-5">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-teal-50 text-teal-700">
                        <IndianRupee className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Financial Exposure &amp; Liability Estimate
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          Calculated under IRDAI health claim guidelines
                        </p>
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      Deterministic
                    </span>
                  </div>

                  {/* 3 Metric Summary Cards */}
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div className="rounded-xl bg-slate-50 p-4 border border-slate-200/70 text-center">
                      <p className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                        Estimated Total Bill
                      </p>
                      <p className="mt-1 text-xl font-extrabold text-slate-900">
                        ₹{result.financial_breakdown.estimated_bill?.toLocaleString('en-IN') || '0'}
                      </p>
                      <span className="text-[10px] text-slate-400">Gross hospital estimate</span>
                    </div>

                    <div className="rounded-xl bg-emerald-50/80 p-4 border border-emerald-200/70 text-center">
                      <p className="text-[11px] font-bold text-emerald-800 uppercase tracking-wider">
                        Insurer Coverage
                      </p>
                      <p className="mt-1 text-xl font-extrabold text-emerald-700">
                        ₹{result.financial_breakdown.estimated_insurer_coverage?.toLocaleString('en-IN') || '0'}
                      </p>
                      <span className="text-[10px] font-semibold text-emerald-700">{insPct}% payable by insurer</span>
                    </div>

                    <div className="rounded-xl bg-rose-50/80 p-4 border border-rose-200/70 text-center">
                      <p className="text-[11px] font-bold text-rose-800 uppercase tracking-wider">
                        Estimated Out-of-Pocket
                      </p>
                      <p className="mt-1 text-xl font-extrabold text-rose-700">
                        ₹{result.financial_breakdown.estimated_out_of_pocket?.toLocaleString('en-IN') || '0'}
                      </p>
                      <span className="text-[10px] font-semibold text-rose-700">{oopPct}% patient liability</span>
                    </div>
                  </div>

                  {/* Visual Liability Stacked Bar */}
                  {billVal > 0 && (
                    <div className="space-y-1.5 pt-1">
                      <div className="flex items-center justify-between text-[11px] font-medium text-slate-600">
                        <span>Liability Distribution</span>
                        <span>{insPct}% Insurer • {oopPct}% Patient</span>
                      </div>
                      <div className="h-3 w-full rounded-full bg-slate-100 flex overflow-hidden p-0.5 border border-slate-200/70">
                        <div
                          className="h-full bg-emerald-500 rounded-l-full transition-all duration-500"
                          style={{ width: `${insPct}%` }}
                          title={`Insurer Payable: ₹${insVal.toLocaleString('en-IN')}`}
                        />
                        <div
                          className="h-full bg-rose-500 rounded-r-full transition-all duration-500"
                          style={{ width: `${oopPct}%` }}
                          title={`Out of Pocket: ₹${oopVal.toLocaleString('en-IN')}`}
                        />
                      </div>
                    </div>
                  )}

                  {/* Deduction Details Ledger */}
                  {result.financial_breakdown.calculation_notes.length > 0 && (
                    <div className="rounded-xl bg-slate-50/80 p-3.5 text-xs text-slate-700 space-y-2 border border-slate-200/70">
                      <div className="flex items-center gap-1.5 font-bold text-slate-800">
                        <ShieldAlert className="h-3.5 w-3.5 text-amber-600" />
                        <span>Itemized Deduction Mechanics:</span>
                      </div>
                      <ul className="space-y-1.5 pl-1 text-[11px]">
                        {result.financial_breakdown.calculation_notes.map((note, nIdx) => (
                          <li key={nIdx} className="flex items-start gap-2 text-slate-700">
                            <span className="text-emerald-600 font-bold">•</span>
                            <span>{note}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <p className="text-[10px] text-slate-400 italic">
                    Disclaimer: Calculations are deterministic estimations based on extracted policy terms and user inputs; not a guarantee of claim settlement by the insurer.
                  </p>
                </div>
              )}

              {/* Applicable Policy Conditions & Restrictions */}
              {result.relevant_conditions.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-50 text-blue-700">
                        <ShieldCheck className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Applicable Policy Conditions &amp; Restrictions
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          Audited rules governing this planned procedure
                        </p>
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      {result.relevant_conditions.length} Conditions
                    </span>
                  </div>

                  <div className="space-y-3">
                    {result.relevant_conditions.map((cond, cIdx) => (
                      <div
                        key={cIdx}
                        className="rounded-xl border border-slate-200/70 bg-slate-50/50 p-4 space-y-1.5 text-xs transition hover:border-slate-300"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="font-bold text-slate-900 text-xs sm:text-sm">
                            {cond.title}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
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
                        </div>
                        <p className="text-slate-600 leading-relaxed text-xs">
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
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Supporting Verbatim Policy Clauses
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          Exact textual citations extracted directly from the contract schedule
                        </p>
                      </div>
                    </div>
                    <span className="rounded-full bg-emerald-50 text-emerald-800 px-2 py-0.5 text-[10px] font-semibold border border-emerald-100">
                      {result.supporting_clauses.length} Citations
                    </span>
                  </div>

                  <div className="space-y-3">
                    {result.supporting_clauses.map((clause, clIdx) => (
                      <div
                        key={clIdx}
                        className="rounded-xl border border-slate-200/80 bg-slate-50/40 p-4 space-y-2 text-xs transition hover:border-slate-300"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="rounded-md bg-emerald-100/80 text-emerald-900 px-2.5 py-0.5 text-[10px] font-bold">
                            Page {clause.page_number} ({clause.chunk_id})
                          </span>
                          {clause.topic && (
                            <span className="text-[11px] font-semibold text-slate-600 bg-white px-2 py-0.5 rounded border border-slate-200/60">
                              {clause.topic}
                            </span>
                          )}
                        </div>
                        <p className="italic text-slate-800 leading-relaxed text-xs border-l-2 border-emerald-500 pl-3 py-0.5">
                          &ldquo;{clause.quote}&rdquo;
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Pre-Admission Preparation Checklist */}
              {result.checklist.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-5">
                  <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
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

                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-emerald-700">
                        {checklistProgress}% Ready
                      </span>
                    </div>
                  </div>

                  {/* Progress bar */}
                  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden border border-slate-200/60">
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
                          className={`rounded-xl border p-3.5 text-xs transition cursor-pointer flex items-start gap-3.5 ${
                            isChecked
                              ? 'border-emerald-200 bg-emerald-50/40 text-slate-600'
                              : 'border-slate-200/90 bg-white hover:border-slate-300 shadow-2xs'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => {}}
                            className="mt-0.5 h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500 shrink-0 cursor-pointer"
                          />
                          <div className="space-y-1.5 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span
                                className={`font-bold text-xs sm:text-sm ${
                                  isChecked ? 'line-through text-slate-500' : 'text-slate-900'
                                }`}
                              >
                                {item.title}
                              </span>
                              {item.is_mandatory && (
                                <span className="rounded-full bg-rose-50 border border-rose-200 px-2 py-0.5 text-[9px] font-bold text-rose-700 uppercase tracking-wider">
                                  Mandatory
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-slate-600 leading-relaxed">
                              {item.description}
                            </p>
                            <div className="rounded-lg bg-emerald-50/60 border border-emerald-100 px-2.5 py-1 text-[11px] text-emerald-900 font-medium inline-block">
                              💡 Action: {item.suggested_action}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Questions to Ask Insurer or TPA Desk */}
              {result.questions_to_ask_tpa.length > 0 && (
                <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-100 pb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-50 text-amber-700">
                        <HelpCircle className="h-4 w-4" />
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-slate-900">
                          Questions to Ask Your Insurer or Hospital TPA Desk
                        </h3>
                        <p className="text-[11px] text-slate-500">
                          Targeted inquiries to prevent cashless pre-authorization disputes
                        </p>
                      </div>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
                      {result.questions_to_ask_tpa.length} Questions
                    </span>
                  </div>

                  <div className="space-y-2.5">
                    {result.questions_to_ask_tpa.map((question, qIdx) => (
                      <div
                        key={qIdx}
                        className="flex items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-slate-50/60 p-3.5 text-xs text-slate-900 hover:border-slate-300 transition"
                      >
                        <span className="font-medium text-xs leading-relaxed">{question}</span>
                        <button
                          type="button"
                          onClick={() => copyQuestion(question, qIdx)}
                          className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-[11px] font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 transition shrink-0 shadow-2xs cursor-pointer"
                          title="Copy question text"
                        >
                          {copiedQuestionIndex === qIdx ? (
                            <>
                              <Check className="h-3.5 w-3.5 text-emerald-600" />
                              <span className="text-emerald-700">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="h-3.5 w-3.5 text-slate-500" />
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
            /* Structured Capabilities Empty State */
            <div className="rounded-2xl border border-slate-200/90 bg-white p-8 shadow-xs space-y-6">
              <div className="text-center max-w-lg mx-auto space-y-2">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 border border-emerald-100 shadow-2xs">
                  <ClipboardCheck className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold text-slate-900">
                  Pre-Admission Claim Intelligence Engine
                </h3>
                <p className="text-xs text-slate-600 leading-relaxed">
                  Choose a clinical preset on the left or enter a planned procedure. CoverScope will cross-examine your policy schedule to evaluate 4 core financial and regulatory dimensions before hospital admission:
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
                <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-4 space-y-1.5 transition hover:border-emerald-300 hover:bg-emerald-50/20">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-xs">
                    <Clock className="h-4 w-4 text-emerald-600" />
                    <span>Waiting Period Clocks</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Verifies 30-day initial, 24-month specific ailment, and 36-month PED clauses against elapsed policy tenure.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-4 space-y-1.5 transition hover:border-amber-300 hover:bg-amber-50/20">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-xs">
                    <Building2 className="h-4 w-4 text-amber-600" />
                    <span>Proportionate Rent Penalty</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Detects room rent tariff sublimits and calculates proportionate deduction risks on doctor, OT, and nursing fees.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-4 space-y-1.5 transition hover:border-teal-300 hover:bg-teal-50/20">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-xs">
                    <IndianRupee className="h-4 w-4 text-teal-600" />
                    <span>IRDAI Co-payment &amp; Sublimits</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Calculates member entry age co-pays strictly on admissible sums to avoid double-charging penalties.
                  </p>
                </div>

                <div className="rounded-xl border border-slate-200/70 bg-slate-50/70 p-4 space-y-1.5 transition hover:border-purple-300 hover:bg-purple-50/20">
                  <div className="flex items-center gap-2 text-slate-900 font-bold text-xs">
                    <ListTodo className="h-4 w-4 text-purple-600" />
                    <span>Cashless Pre-Auth Checklist</span>
                  </div>
                  <p className="text-[11px] text-slate-600 leading-relaxed">
                    Generates mandatory documentation requirements, TPA inquiries, and estimated out-of-pocket cash requirements.
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-center gap-2 pt-2 text-[11px] text-slate-500 border-t border-slate-100">
                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                <span>Backed by deterministic rule extraction • Zero generative hallucinations</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Rehearsal History Section */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
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
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition ${
                historyFilterPolicyOnly
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-800'
                  : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
              }`}
              title={historyFilterPolicyOnly ? 'Showing current policy only' : 'Showing all policies'}
            >
              <Filter className="h-3.5 w-3.5" />
              <span>{historyFilterPolicyOnly ? 'Current Policy Only' : 'All Policies'}</span>
            </button>

            <button
              type="button"
              onClick={() => fetchHistory(historyFilterPolicyOnly ? (selectedPolicyId || undefined) : undefined)}
              disabled={isLoadingHistory}
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition disabled:opacity-50"
              title="Refresh rehearsal history"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${isLoadingHistory ? 'animate-spin' : ''}`} />
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
          <div className="overflow-x-auto rounded-xl border border-slate-200/80">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50/90 border-b border-slate-200 text-slate-600 font-semibold uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-3 px-4">Date &amp; Time</th>
                  <th className="py-3 px-4">Policy Document</th>
                  <th className="py-3 px-4">Planned Treatment</th>
                  <th className="py-3 px-4">Estimated Bill</th>
                  <th className="py-3 px-4">Readiness Status</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-slate-700 bg-white">
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
                    <tr key={rec.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <Calendar className="h-3.5 w-3.5 text-slate-400" />
                          <span>{dateStr}</span>
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-800 max-w-[180px] truncate" title={policyName}>
                        {policyName}
                      </td>
                      <td className="py-3.5 px-4 font-semibold text-slate-900 max-w-[220px] truncate" title={treatmentDesc}>
                        {treatmentDesc}
                      </td>
                      <td className="py-3.5 px-4 text-slate-800 font-semibold whitespace-nowrap">
                        {exp}
                      </td>
                      <td className="py-3.5 px-4 whitespace-nowrap">
                        {renderReadinessBadge(rec.result_summary?.readiness_status)}
                      </td>
                      <td className="py-3.5 px-4 text-right whitespace-nowrap">
                        <button
                          type="button"
                          onClick={() => setSelectedRecord(rec)}
                          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 hover:border-emerald-300 transition shadow-2xs cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
          <div className="relative w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl border border-slate-200">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-100 pb-4">
              <div>
                <div className="flex items-center gap-2 mb-1.5">
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
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Estimated Bill</span>
                    <span className="font-bold text-slate-900">
                      {selectedRecord.input_summary?.estimated_expense ? `₹${Number(selectedRecord.input_summary.estimated_expense).toLocaleString('en-IN')}` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Member Age</span>
                    <span className="font-bold text-slate-900">
                      {selectedRecord.input_summary?.member_age ? `${selectedRecord.input_summary.member_age} yrs` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Policy Tenure</span>
                    <span className="font-bold text-slate-900">
                      {selectedRecord.input_summary?.policy_duration_months ? `${selectedRecord.input_summary.policy_duration_months} mos` : 'Not specified'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Room Category</span>
                    <span className="font-bold text-slate-900 capitalize">
                      {selectedRecord.input_summary?.room_category?.replace(/_/g, ' ') || 'Single Private'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Hospital Type</span>
                    <span className="font-bold text-slate-900 capitalize">
                      {selectedRecord.input_summary?.hospital_type?.replace(/_/g, ' ') || 'Network Cashless'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Pre-Existing Condition</span>
                    <span className={`font-bold ${selectedRecord.input_summary?.is_pre_existing ? 'text-amber-700' : 'text-slate-800'}`}>
                      {selectedRecord.input_summary?.is_pre_existing ? 'Yes' : 'No'}
                    </span>
                  </div>
                  <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-100">
                    <span className="block text-[10px] text-slate-400 font-medium">Emergency Admission</span>
                    <span className="font-bold text-slate-800">
                      {selectedRecord.input_summary?.is_emergency ? 'Yes' : 'No'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Financial Snapshot if available */}
              {selectedRecord.result_summary?.financial_breakdown && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4">
                  <h4 className="font-semibold text-emerald-900 mb-2.5 flex items-center gap-1.5">
                    <IndianRupee className="h-3.5 w-3.5 text-emerald-700" />
                    Recorded Financial Breakdown
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {selectedRecord.result_summary.financial_breakdown.estimated_bill != null && (
                      <div className="bg-white p-3 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] font-semibold text-slate-500 uppercase">Total Billed</span>
                        <span className="font-bold text-slate-900 text-sm">₹{Number(selectedRecord.result_summary.financial_breakdown.estimated_bill).toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    {selectedRecord.result_summary.financial_breakdown.deductible_or_copay_amount != null && (
                      <div className="bg-white p-3 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] font-semibold text-slate-500 uppercase">Deductible / Co-pay</span>
                        <span className="font-bold text-rose-700 text-sm">₹{Number(selectedRecord.result_summary.financial_breakdown.deductible_or_copay_amount).toLocaleString('en-IN')}</span>
                      </div>
                    )}
                    {selectedRecord.result_summary.financial_breakdown.copayment_percentage != null && (
                      <div className="bg-white p-3 rounded-lg border border-emerald-100">
                        <span className="block text-[10px] font-semibold text-slate-500 uppercase">Co-pay %</span>
                        <span className="font-bold text-amber-700 text-sm">{selectedRecord.result_summary.financial_breakdown.copayment_percentage}%</span>
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
                      <div key={idx} className="rounded-lg bg-slate-50 p-3 border border-slate-100 text-slate-700">
                        <div className="flex items-center justify-between text-[11px] font-semibold text-slate-800 mb-1">
                          <span>{clause.topic || `Clause ${clause.chunk_id || idx + 1}`}</span>
                          {clause.page_number && (
                            <span className="text-[10px] text-slate-500 font-bold bg-white px-2 py-0.5 rounded border border-slate-200/60">
                              Page {clause.page_number}
                            </span>
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
                className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-600 bg-emerald-50 px-3.5 py-2 text-xs font-bold text-emerald-700 hover:bg-emerald-100 transition shadow-2xs cursor-pointer"
              >
                <ClipboardCheck className="h-3.5 w-3.5" />
                <span>Load Parameters into Form</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedRecord(null)}
                className="rounded-xl bg-slate-100 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-200 transition cursor-pointer"
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
