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
          setPolicyBId(id);
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

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'comparable') {
      return (
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
          Comparable Terms
        </span>
      );
    }
    if (s === 'condition_dependent') {
      return (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold text-amber-800">
          Condition Dependent
        </span>
      );
    }
    if (s === 'missing_from_documents') {
      return (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-700">
          Missing From Documents
        </span>
      );
    }
    if (s === 'needs_review') {
      return (
        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-semibold text-blue-800">
          Needs Review
        </span>
      );
    }
    if (s === 'not_applicable') {
      return (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-600">
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
        <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-bold uppercase text-rose-800">
          Caution
        </span>
      );
    }
    if (s === 'conditional_gap') {
      return (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold uppercase text-amber-800">
          Conditional Gap
        </span>
      );
    }
    if (s === 'unverified_gap') {
      return (
        <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase text-blue-800">
          Unverified Gap
        </span>
      );
    }
    return (
      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase text-slate-700">
        Informational
      </span>
    );
  };

  const policyA = policies.find((p) => (p.policy_id || p.id) === policyAId);
  const policyB = policies.find((p) => (p.policy_id || p.id) === policyBId);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">Policy Comparison</h1>
        <p className="text-sm text-slate-500 mt-0.5">
          Side-by-side dimensional analysis and protection gap detection across health policy contracts.
        </p>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Notice when fewer than 2 policies are available */}
      {policies.length < 2 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-600 mt-0.5" />
          <div className="space-y-1">
            <p className="font-semibold">Two distinct policies are required for side-by-side comparison.</p>
            <p className="text-amber-800 leading-relaxed">
              You currently have {policies.length} policy in your library. Please{' '}
              <Link to="/library" className="font-bold underline text-emerald-800 hover:text-emerald-950">
                upload a second policy schedule in the Document Library
              </Link>{' '}
              to unlock side-by-side gap detection, sub-limit comparisons, and waiting period auditing.
            </p>
          </div>
        </div>
      )}

      {/* Configuration Card */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-xs">
        <form onSubmit={handleCompare} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Policy A */}
            <div className="rounded-lg bg-emerald-50/50 p-4 border border-emerald-100">
              <label className="block text-xs font-bold text-emerald-800 uppercase tracking-wider mb-1.5">
                Baseline Policy (Policy A)
              </label>
              <select
                value={policyAId}
                onChange={(e) => setPolicyAId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 px-3 text-xs font-medium text-slate-800 focus:border-emerald-500 focus:outline-none"
              >
                {policies.map((p) => {
                  const id = p.policy_id || p.id || '';
                  const name = p.filename || p.document_name || 'Policy Document';
                  return (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Policy B */}
            <div className="rounded-lg bg-blue-50/50 p-4 border border-blue-100">
              <label className="block text-xs font-bold text-blue-800 uppercase tracking-wider mb-1.5">
                Comparison Policy (Policy B)
              </label>
              <select
                value={policyBId}
                onChange={(e) => setPolicyBId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 bg-white py-2 px-3 text-xs font-medium text-slate-800 focus:border-blue-500 focus:outline-none"
              >
                {policies.map((p) => {
                  const id = p.policy_id || p.id || '';
                  const name = p.filename || p.document_name || 'Policy Document';
                  return (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  );
                })}
              </select>
            </div>
          </div>

          {/* Assumptions */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-1">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Continuous Coverage Duration (Months)
              </label>
              <input
                type="number"
                min={0}
                max={120}
                value={continuousMonths}
                onChange={(e) => setContinuousMonths(parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-300 py-1.5 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Insured Member Entry Age (Years)
              </label>
              <input
                type="number"
                min={1}
                max={100}
                value={entryAge}
                onChange={(e) => setEntryAge(parseInt(e.target.value) || 0)}
                className="w-full rounded-lg border border-slate-300 py-1.5 px-3 text-xs text-slate-800 focus:border-emerald-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={isComparing || !policyAId || !policyBId}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white shadow hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isComparing ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Comparing Dimensions...</span>
                </>
              ) : (
                <>
                  <GitCompare className="h-4 w-4" />
                  <span>Run Comparison</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Comparison Results */}
      {result && (
        <div className="space-y-6">
          {/* Protection Gap Alerts */}
          {result.gaps && result.gaps.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-700 flex items-center gap-2">
                <ShieldAlert className="h-4 w-4 text-amber-600" />
                <span>Detected Protection Gaps ({result.gaps.length})</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {result.gaps.map((gap, i) => (
                  <div
                    key={i}
                    className="rounded-xl border border-amber-200 bg-amber-50/50 p-4 shadow-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-xs text-amber-900">{gap.title}</span>
                      {getGapSeverityBadge(gap.severity)}
                    </div>
                    <p className="text-xs text-amber-800 leading-relaxed">{gap.description}</p>
                    <p className="text-[10px] text-amber-600 font-mono">Dimension: {gap.dimension}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Matrix Table */}
          <div className="rounded-xl border border-slate-200/80 bg-white shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Side-by-Side Dimension Matrix</h3>
                <p className="text-xs text-slate-500">Evaluation under {continuousMonths} months continuous coverage</p>
              </div>
              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800">
                {result.dimensions.length} dimensions · {result.gaps.length} gap
                {result.gaps.length === 1 ? '' : 's'}
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-700 border-b border-slate-200">
                  <tr>
                    <th className="py-3 px-4 font-semibold w-1/4">Coverage Dimension</th>
                    <th className="py-3 px-4 font-semibold w-1/4 text-emerald-800 bg-emerald-50/40">
                      Policy A ({policyA?.filename || policyA?.document_name || result.policy_a_name})
                    </th>
                    <th className="py-3 px-4 font-semibold w-1/4 text-blue-800 bg-blue-50/40">
                      Policy B ({policyB?.filename || policyB?.document_name || result.policy_b_name})
                    </th>
                    <th className="py-3 px-4 font-semibold w-1/4">Assessment</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {result.dimensions.map((dim, idx) => (
                    <tr key={idx} className="hover:bg-slate-50/50">
                      <td className="py-3 px-4 font-medium text-slate-900">
                        <div className="space-y-1">
                          <p className="font-semibold">{dim.name}</p>
                          <div>{getStatusBadge(dim.status)}</div>
                        </div>
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-800 bg-emerald-50/20">
                        {dim.policy_a_value}
                      </td>
                      <td className="py-3 px-4 font-medium text-slate-800 bg-blue-50/20">
                        {dim.policy_b_value}
                      </td>
                      <td className="py-3 px-4 text-slate-600 leading-relaxed">
                        {dim.assessment}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
