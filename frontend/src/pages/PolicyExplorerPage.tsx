import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  FileText,
  ChevronLeft,
  ChevronRight,
  Search,
  Filter,
  CheckCircle2,
  AlertCircle,
  Layers,
  BookOpen,
  Trash2,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, PolicyFactItem, PolicyPageTextResponse } from '../lib/types';

export const PolicyExplorerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'reader' | 'facts'>('facts');

  // Reader state
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [pageData, setPageData] = useState<PolicyPageTextResponse | null>(null);
  const [isLoadingPage, setIsLoadingPage] = useState<boolean>(false);

  // Facts state
  const [facts, setFacts] = useState<PolicyFactItem[]>([]);
  const [isLoadingFacts, setIsLoadingFacts] = useState<boolean>(false);
  const [factCategoryFilter, setFactCategoryFilter] = useState<string>('all');
  const [factSearch, setFactSearch] = useState<string>('');

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
      }
    }
    loadPolicies();
  }, [searchParams]);

  // Load facts whenever selectedPolicyId changes
  useEffect(() => {
    if (!selectedPolicyId) return;
    async function loadFacts() {
      setIsLoadingFacts(true);
      setErrorMsg(null);
      try {
        const res = await api.getPolicyFacts(selectedPolicyId);
        setFacts(res.facts || []);
      } catch (err: any) {
        console.warn('Failed to load policy facts:', err);
      } finally {
        setIsLoadingFacts(false);
      }
    }
    loadFacts();
    setCurrentPage(1);
  }, [selectedPolicyId]);

  // Load page text whenever currentPage or selectedPolicyId changes
  useEffect(() => {
    if (!selectedPolicyId || activeTab !== 'reader') return;
    async function loadPage() {
      setIsLoadingPage(true);
      try {
        const res = await api.getPolicyPageText(selectedPolicyId, currentPage);
        setPageData(res);
      } catch (err: any) {
        setErrorMsg('Failed to fetch page text.');
      } finally {
        setIsLoadingPage(false);
      }
    }
    loadPage();
  }, [selectedPolicyId, currentPage, activeTab]);

  const currentPolicy = policies.find((p) => (p.policy_id || p.id) === selectedPolicyId);
  const isCurrentBundled = currentPolicy?.status === 'bundled';
  const totalPages = currentPolicy?.page_count || 1;

  const handleDeleteSelectedPolicy = async () => {
    if (!currentPolicy) return;
    const name = currentPolicy.filename || currentPolicy.document_name || 'Policy Document';
    if (
      !window.confirm(
        `Permanently delete policy "${name}" from your MongoDB database and storage?\n\nThis will purge all pages, indexed chunks, and facts. This action cannot be undone.`
      )
    ) {
      return;
    }
    try {
      await api.deletePolicy(selectedPolicyId);
      const remaining = policies.filter(
        (p) => (p.policy_id || p.id) !== selectedPolicyId && p.id !== selectedPolicyId
      );
      setPolicies(remaining);
      if (remaining.length > 0) {
        setSelectedPolicyId(remaining[0].policy_id || remaining[0].id || '');
      } else {
        setSelectedPolicyId('');
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to delete policy.');
    }
  };

  const categories = Array.from(new Set(facts.map((f) => f.category)));
  const filteredFacts = facts.filter((f) => {
    const matchesCat = factCategoryFilter === 'all' || f.category === factCategoryFilter;
    const matchesQuery = f.text.toLowerCase().includes(factSearch.toLowerCase());
    return matchesCat && matchesQuery;
  });

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Policy Explorer</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Browse raw document pages and inspect extracted candidate facts and condition clauses.
          </p>
        </div>

        {/* Policy Selector & Quick Actions */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-600 whitespace-nowrap">Select Document:</label>
          {policies.length > 0 ? (
            <>
              <select
                value={selectedPolicyId}
                onChange={(e) => setSelectedPolicyId(e.target.value)}
                className="rounded-lg border border-slate-300 bg-white py-1.5 px-3 text-xs font-medium text-slate-800 shadow-xs focus:border-emerald-500 focus:outline-none"
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
              {currentPolicy && !isCurrentBundled && (
                <button
                  onClick={handleDeleteSelectedPolicy}
                  title="Permanently delete this policy from database and storage"
                  className="inline-flex items-center gap-1 rounded-lg border border-rose-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 hover:border-rose-300 transition"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  <span>Delete</span>
                </button>
              )}
            </>
          ) : (
            <Link
              to="/library"
              className="text-xs font-semibold text-emerald-600 hover:underline"
            >
              Upload a policy first &rarr;
            </Link>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex space-x-6 text-sm">
          <button
            onClick={() => setActiveTab('facts')}
            className={`flex items-center gap-2 border-b-2 py-3 px-1 font-semibold transition ${
              activeTab === 'facts'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Layers className="h-4 w-4" />
            <span>Extracted Facts &amp; Clauses ({facts.length})</span>
          </button>

          <button
            onClick={() => setActiveTab('reader')}
            className={`flex items-center gap-2 border-b-2 py-3 px-1 font-semibold transition ${
              activeTab === 'reader'
                ? 'border-emerald-600 text-emerald-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <BookOpen className="h-4 w-4" />
            <span>Page Reader</span>
          </button>
        </nav>
      </div>

      {/* TAB 1: EXTRACTED FACTS */}
      {activeTab === 'facts' && (
        <div className="space-y-4">
          {/* Filter Bar */}
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-xl border border-slate-200/80 bg-white p-3 shadow-xs">
            <div className="flex items-center gap-2 w-full sm:w-auto">
              <Filter className="h-4 w-4 text-slate-400" />
              <select
                value={factCategoryFilter}
                onChange={(e) => setFactCategoryFilter(e.target.value)}
                className="rounded-lg border border-slate-200 bg-slate-50 py-1.5 px-3 text-xs text-slate-700 focus:outline-none"
              >
                <option value="all">All Categories</option>
                {categories.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>

            <div className="relative w-full sm:w-72">
              <Search className="pointer-events-none absolute left-3 top-2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                placeholder="Filter propositions..."
                value={factSearch}
                onChange={(e) => setFactSearch(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-slate-50 py-1.5 pl-8 pr-3 text-xs text-slate-800 focus:outline-none focus:bg-white"
              />
            </div>
          </div>

          {isLoadingFacts ? (
            <div className="p-12 text-center text-xs text-slate-500">
              <div className="mx-auto h-5 w-5 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent mb-2" />
              Extracting candidate facts...
            </div>
          ) : filteredFacts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredFacts.map((fact, index) => (
                <div
                  key={index}
                  className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-xs flex flex-col justify-between hover:border-slate-300 transition"
                >
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                        {fact.category}
                      </span>
                      <span className="text-[11px] font-medium text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                        Page {fact.page_number}
                      </span>
                    </div>
                    <p className="text-xs text-slate-800 leading-relaxed font-medium">
                      {fact.text}
                    </p>
                  </div>

                  <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-emerald-600" />
                      Grounded candidate
                    </span>
                    <span>Confidence: {(fact.confidence * 100).toFixed(0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 p-8 text-center text-xs text-slate-500">
              No policy facts found matching your criteria.
            </div>
          )}
        </div>
      )}

      {/* TAB 2: PAGE READER */}
      {activeTab === 'reader' && (
        <div className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4">
          {/* Reader Pagination Controls */}
          <div className="flex items-center justify-between border-b border-slate-100 pb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-700">
                Page {currentPage} of {totalPages}
              </span>
              {pageData && (
                <span className="text-[11px] text-slate-400">
                  ({pageData.char_count.toLocaleString()} characters)
                </span>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                disabled={currentPage <= 1 || isLoadingPage}
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                <span>Previous</span>
              </button>
              <button
                disabled={currentPage >= totalPages || isLoadingPage}
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40"
              >
                <span>Next</span>
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          {/* Reader Content Area */}
          {isLoadingPage ? (
            <div className="py-16 text-center text-xs text-slate-500">
              <div className="mx-auto h-5 w-5 animate-spin rounded-full border-2 border-emerald-600 border-t-transparent mb-2" />
              Loading page {currentPage}...
            </div>
          ) : pageData ? (
            <div className="rounded-lg bg-slate-50 p-6 border border-slate-200/60 font-mono text-xs leading-relaxed text-slate-800 whitespace-pre-wrap max-h-[600px] overflow-y-auto">
              {pageData.text || 'No text extracted on this page.'}
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-slate-500">
              Select a page to view extracted content.
            </div>
          )}
        </div>
      )}
    </div>
  );
};
