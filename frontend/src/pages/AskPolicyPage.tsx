import React, { useEffect, useState } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  MessageSquare,
  Send,
  ShieldCheck,
  FileText,
  AlertCircle,
  HelpCircle,
  Sparkles,
  Quote,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, AnswerResponse } from '../lib/types';

interface QAMessage {
  question: string;
  response: AnswerResponse;
  timestamp: string;
}

export const AskPolicyPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [policies, setPolicies] = useState<PolicySummary[]>([]);
  const [selectedPolicyId, setSelectedPolicyId] = useState<string>('');
  const [question, setQuestion] = useState('');
  const [isLoadingPolicies, setIsLoadingPolicies] = useState(true);
  const [isAsking, setIsAsking] = useState(false);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Suggested question prompts
  const samplePrompts = [
    'Is cataract surgery covered under this policy?',
    'What is the waiting period for pre-existing diseases (PED)?',
    'Are maternity expenses or newborn child care covered?',
    'What are the room rent sub-limits and ICU caps?',
    'Are organ donor hospitalization expenses payable?',
  ];

  useEffect(() => {
    async function loadPolicies() {
      try {
        setIsLoadingPolicies(true);
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
        setErrorMsg('Failed to load policies. Please ensure backend is active.');
      } finally {
        setIsLoadingPolicies(false);
      }
    }
    loadPolicies();
  }, [searchParams]);

  // Load conversation history from MongoDB Atlas whenever the selected policy changes
  useEffect(() => {
    if (!selectedPolicyId) {
      setMessages([]);
      return;
    }
    async function loadHistory() {
      try {
        const hist = await api.getChatHistory(selectedPolicyId);
        if (hist.messages && hist.messages.length > 0) {
          const restored: QAMessage[] = [];
          for (let i = 0; i < hist.messages.length; i++) {
            const m = hist.messages[i];
            if (m.role === 'user') {
              const nextMsg = hist.messages[i + 1];
              if (nextMsg && nextMsg.role === 'assistant') {
                const em = nextMsg.evidence_metadata || {};
                restored.push({
                  question: m.content,
                  timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString() : '',
                  response: {
                    verdict: em.verdict || 'not_stated',
                    answer: nextMsg.content,
                    confidence: em.confidence || 'medium',
                    citations: em.citations || [],
                    caveats: em.caveats || [],
                    citations_valid: em.citations_valid ?? true,
                    manual_review_required: em.manual_review_required ?? false,
                    warnings: em.warnings || [],
                    unverified_answer: em.unverified_answer || null,
                  },
                });
                i++;
              }
            }
          }
          // Newest messages render at top
          setMessages(restored.reverse());
        } else {
          setMessages([]);
        }
      } catch (err) {
        console.debug('No prior chat history for policy:', err);
      }
    }
    loadHistory();
  }, [selectedPolicyId]);

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || question).trim();
    if (!q) return;

    if (!selectedPolicyId) {
      setErrorMsg('Please select a policy document to ask.');
      return;
    }

    setIsAsking(true);
    setErrorMsg(null);

    try {
      const res = await api.askQuestion(selectedPolicyId, q);
      setMessages((prev) => [
        {
          question: q,
          response: res,
          timestamp: new Date().toLocaleTimeString(),
        },
        ...prev,
      ]);
      setQuestion('');
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve answer from policy.');
    } finally {
      setIsAsking(false);
    }
  };

  const renderVerdictBadge = (verdict: string) => {
    const v = verdict.toLowerCase();
    if (v === 'covered') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          Covered
        </span>
      );
    }
    if (v === 'excluded') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-100 px-2.5 py-0.5 text-xs font-semibold text-rose-800">
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          Permanently Excluded
        </span>
      );
    }
    if (v === 'depends') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-800">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
          Conditional / Depends
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-700">
        <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
        Not Stated in Policy
      </span>
    );
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Ask My Policy</h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Get factual answers with exact page citations verified against your policy schedule.
          </p>
        </div>

        {/* Policy Selector */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold text-slate-600 whitespace-nowrap">Target Policy:</label>
          {isLoadingPolicies ? (
            <div className="h-9 w-48 animate-pulse rounded-lg bg-slate-200" />
          ) : policies.length > 0 ? (
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

      {/* Error alert */}
      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Question Input Card */}
      <div className="rounded-xl border border-slate-200/80 bg-white p-5 shadow-xs">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleAsk();
          }}
          className="space-y-3"
        >
          <div className="relative">
            <textarea
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Is robotic knee surgery covered under this policy, and what are the specific conditions or waiting periods?"
              className="w-full rounded-lg border border-slate-300 p-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/20"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
            />
          </div>

          <div className="flex flex-col sm:flex-row items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-500">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              <span>Prompt suggestions:</span>
              {samplePrompts.slice(0, 2).map((prompt, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleAsk(prompt)}
                  className="rounded-md border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-700 hover:border-emerald-500 hover:bg-emerald-50 hover:text-emerald-800 transition"
                >
                  {prompt}
                </button>
              ))}
            </div>

            <button
              type="submit"
              disabled={isAsking || !question.trim() || !selectedPolicyId}
              className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow hover:bg-emerald-700 disabled:opacity-50 transition"
            >
              {isAsking ? (
                <>
                  <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Searching Clauses...</span>
                </>
              ) : (
                <>
                  <Send className="h-3.5 w-3.5" />
                  <span>Ask Policy</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Consultation Results */}
      <div className="space-y-4">
        {messages.length > 0 ? (
          messages.map((item, index) => (
            <div
              key={index}
              className="rounded-xl border border-slate-200/80 bg-white p-6 shadow-xs space-y-4"
            >
              {/* Question header */}
              <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-3">
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-slate-100 text-slate-600 shrink-0 mt-0.5">
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-bold text-slate-900">{item.question}</h3>
                    <p className="text-[10px] text-slate-400 mt-0.5">Asked at {item.timestamp}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                    Confidence: {item.response.confidence}
                  </span>
                  {renderVerdictBadge(item.response.verdict)}
                </div>
              </div>

              {/* Synthesized Answer */}
              <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-line bg-slate-50/60 p-4 rounded-lg border border-slate-100">
                {item.response.answer}
              </div>

              {/* Manual review banner for unverified answers */}
              {item.response.manual_review_required && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900 space-y-2">
                  <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Manual Review Required</span>
                  </div>
                  <p className="leading-relaxed">
                    This answer is not a definitive coverage decision. Verify the cited policy
                    wording manually before relying on it.
                  </p>
                  {item.response.warnings.length > 0 && (
                    <ul className="list-disc list-inside space-y-1">
                      {item.response.warnings.map((warning, wIndex) => (
                        <li key={wIndex}>{warning}</li>
                      ))}
                    </ul>
                  )}
                  {item.response.unverified_answer && (
                    <details className="pt-1">
                      <summary className="cursor-pointer font-semibold">
                        Show the unverified model answer
                      </summary>
                      <p className="mt-1.5 whitespace-pre-line italic text-amber-800">
                        {item.response.unverified_answer}
                      </p>
                    </details>
                  )}
                </div>
              )}

              {/* Caveats and warnings */}
              {item.response.caveats?.length > 0 && (
                <div className="rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600">
                  <p className="font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                    Caveats
                  </p>
                  <ul className="list-disc list-inside space-y-1">
                    {item.response.caveats.map((caveat, cavIndex) => (
                      <li key={cavIndex}>{caveat}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Grounded Evidence Citations */}
              {item.response.citations && item.response.citations.length > 0 && (
                <div className="space-y-2 pt-2">
                  <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-slate-500">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" />
                    <span>Verbatim Policy Citations ({item.response.citations.length})</span>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {item.response.citations.map((cite, cIndex) => (
                      <div
                        key={cIndex}
                        className="rounded-lg border border-slate-200/80 bg-white p-3 shadow-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="font-semibold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded">
                            Page {cite.page_number}
                          </span>
                          <span className="font-mono text-slate-400">
                            {cite.chunk_id}
                          </span>
                        </div>
                        <p className="text-xs text-slate-600 italic border-l-2 border-emerald-400 pl-2.5">
                          &ldquo;{cite.quote}&rdquo;
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-slate-200 p-12 text-center">
            <MessageSquare className="mx-auto h-8 w-8 text-slate-300" />
            <h3 className="mt-3 text-sm font-semibold text-slate-700">No Questions Asked Yet</h3>
            <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
              Type any health insurance coverage question above or select a suggested prompt to inspect
              verbatim citations from your policy schedule.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};
