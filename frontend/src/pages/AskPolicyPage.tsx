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
  RotateCcw,
  Clock,
  Copy,
  Check,
  Search,
  BookOpen,
  ArrowRight,
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
  const [question, setQuestion] = useState(searchParams.get('q') || '');
  const [isLoadingPolicies, setIsLoadingPolicies] = useState(true);
  const [isAsking, setIsAsking] = useState(false);
  const [messages, setMessages] = useState<QAMessage[]>([]);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [copiedCitationIndex, setCopiedCitationIndex] = useState<string | null>(null);

  // Suggested clinical question prompts
  const samplePrompts = [
    { label: 'Cataract Sublimits', query: 'Is cataract surgery covered under this policy, and what are the monetary limits?' },
    { label: 'PED Waiting Period', query: 'What is the waiting period for pre-existing diseases (PED)?' },
    { label: 'Room Rent Deductions', query: 'What are the room rent sub-limits and proportionate deduction rules?' },
    { label: 'Maternity & Newborn', query: 'Are maternity expenses or newborn child hospitalization covered?' },
  ];

  // Update question if 'q' search param changes
  useEffect(() => {
    const qParam = searchParams.get('q');
    if (qParam) {
      setQuestion(qParam);
    }
  }, [searchParams]);

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
              const nextMsg = i + 1 < hist.messages.length && hist.messages[i + 1].role === 'assistant'
                ? hist.messages[i + 1]
                : null;

              if (nextMsg) {
                const em = nextMsg.evidence_metadata || {};
                restored.push({
                  question: m.content,
                  timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
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
                i++; // Safely advance past paired assistant reply
              } else {
                restored.push({
                  question: m.content,
                  timestamp: m.created_at ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
                  response: {
                    verdict: 'not_stated',
                    answer: 'Response could not be completed during session.',
                    confidence: 'low',
                    citations: [],
                    caveats: ['Incomplete conversation turn recorded.'],
                    citations_valid: false,
                    manual_review_required: true,
                    warnings: [],
                    unverified_answer: null,
                  },
                });
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
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
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

  const handleClearChat = async () => {
    if (!selectedPolicyId || messages.length === 0) return;
    if (!window.confirm('Clear consultation history for this policy?')) return;
    setErrorMsg('');
    try {
      await api.clearChatHistory(selectedPolicyId);
      setMessages([]);
    } catch (err: any) {
      console.error('Failed to clear remote chat history:', err);
      setErrorMsg(err.message || 'Failed to clear conversation history. Please try again.');
    }
  };

  const copyCitation = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCitationIndex(id);
    setTimeout(() => setCopiedCitationIndex(null), 2000);
  };

  const renderVerdictBadge = (verdict: string) => {
    const v = verdict.toLowerCase();
    if (v === 'covered') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100/90 px-3 py-0.5 text-xs font-bold text-emerald-800 border border-emerald-200 shadow-2xs">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          Covered
        </span>
      );
    }
    if (v === 'excluded') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100/90 px-3 py-0.5 text-xs font-bold text-rose-800 border border-rose-200 shadow-2xs">
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          Permanently Excluded
        </span>
      );
    }
    if (v === 'depends') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100/90 px-3 py-0.5 text-xs font-bold text-amber-900 border border-amber-200 shadow-2xs">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
          Conditional / Depends
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-0.5 text-xs font-semibold text-slate-700 border border-slate-200 shadow-2xs">
        <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
        Not Stated in Policy
      </span>
    );
  };

  const currentPolicy = policies.find((p) => (p.policy_id || p.id) === selectedPolicyId);

  return (
    <div className="space-y-8 animate-in fade-in-50 duration-200">
      {/* Page Header with Telemetry & Integrated Target Policy Ribbon */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200/80 pb-6">
        <div className="space-y-1.5">
          <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200/80 px-3 py-1 text-xs font-semibold text-emerald-800">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
            </span>
            <span>Verbatim Semantic Grounding</span>
            <span className="text-emerald-300">•</span>
            <span className="text-emerald-700/80 font-normal">250k Token Context</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            Ask My Policy
          </h1>
          <p className="text-sm text-slate-600 max-w-2xl leading-relaxed">
            Interrogate policy schedules with natural questions. CoverScope verifies coverage, waiting periods, and exclusions against verbatim page text with exact citations.
          </p>
        </div>

        {/* Policy Selector Card */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
          <div className="flex items-center gap-2 rounded-xl border border-slate-200/90 bg-white p-2 shadow-xs">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 shrink-0">
              <FileText className="h-4 w-4" />
            </div>
            <div className="flex-1 min-w-[200px] max-w-[280px]">
              <label htmlFor="target-policy-qa" className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Active Document
              </label>
              {isLoadingPolicies ? (
                <div className="h-5 w-32 animate-pulse rounded bg-slate-200" />
              ) : policies.length > 0 ? (
                <select
                  id="target-policy-qa"
                  value={selectedPolicyId}
                  onChange={(e) => setSelectedPolicyId(e.target.value)}
                  className="w-full bg-transparent text-xs font-semibold text-slate-900 focus:outline-hidden truncate cursor-pointer"
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
                <Link to="/library" className="text-xs font-semibold text-emerald-700 hover:underline">
                  Upload a policy &rarr;
                </Link>
              )}
            </div>
          </div>

          {messages.length > 0 && (
            <button
              type="button"
              onClick={handleClearChat}
              title="Clear consultation history"
              className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 hover:text-slate-900 transition shadow-xs cursor-pointer shrink-0"
            >
              <RotateCcw className="h-3.5 w-3.5 text-slate-500" />
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Error alert */}
      {errorMsg && (
        <div className="flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 shadow-xs">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {/* Query Console Card */}
      <div className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4">
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
              placeholder="e.g. Is robotic knee surgery covered under this policy, and what are the specific sub-limits or waiting periods?"
              className="w-full rounded-xl border border-slate-200 bg-white p-3.5 text-sm font-medium text-slate-900 placeholder:text-slate-400 transition hover:border-slate-300 focus:border-emerald-600 focus:outline-hidden focus:ring-1 focus:ring-emerald-600"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAsk();
                }
              }}
            />
            <div className="absolute right-3 bottom-3 hidden sm:flex items-center gap-1.5 text-[10px] text-slate-400 font-medium select-none pointer-events-none">
              <span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5">Enter ↵</span>
              <span>to search</span>
            </div>
          </div>

          {/* Quick Preset Prompts Rack */}
          <div className="space-y-2 pt-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
              <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
              <span>Suggested Inquiries:</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
              {samplePrompts.map((preset, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleAsk(preset.query)}
                  className="flex items-center justify-between rounded-xl border border-slate-200/90 bg-slate-50/70 p-2.5 text-left text-xs font-medium text-slate-700 hover:border-emerald-500 hover:bg-emerald-50/40 hover:text-emerald-950 transition-all shadow-2xs group"
                >
                  <span className="font-semibold text-[11px] truncate pr-1 text-slate-800 group-hover:text-emerald-900">
                    + {preset.label}
                  </span>
                  <ArrowRight className="h-3 w-3 text-slate-400 group-hover:text-emerald-600 shrink-0" />
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between pt-2 border-t border-slate-100">
            <span className="text-[11px] text-slate-400 hidden sm:inline">
              Verified against: <strong className="text-slate-600">{currentPolicy?.filename || 'Loaded Policy'}</strong>
            </span>

            <button
              type="submit"
              disabled={isAsking || !question.trim() || !selectedPolicyId}
              className="w-full sm:w-auto flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white shadow-xs hover:bg-emerald-700 hover:shadow-md disabled:opacity-50 transition-all cursor-pointer"
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

      {/* Consultation Results Stream */}
      <div className="space-y-5">
        {messages.length > 0 ? (
          messages.map((item, index) => (
            <div
              key={index}
              className="rounded-2xl border border-slate-200/90 bg-white p-6 shadow-xs space-y-4"
            >
              {/* Question Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                <div className="flex items-start gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 shrink-0 shadow-2xs">
                    <MessageSquare className="h-4 w-4" />
                  </div>
                  <div>
                    <h3 className="text-sm sm:text-base font-bold text-slate-900 leading-snug">
                      {item.question}
                    </h3>
                    <div className="flex items-center gap-2 text-[10px] text-slate-400 mt-1">
                      <Clock className="h-3 w-3" />
                      <span>Asked at {item.timestamp}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-center shrink-0">
                  <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                    Confidence: {item.response.confidence}
                  </span>
                  {renderVerdictBadge(item.response.verdict)}
                </div>
              </div>

              {/* Synthesized Answer */}
              <div className="rounded-xl bg-slate-50/70 p-4 border border-slate-200/60 text-sm text-slate-800 leading-relaxed whitespace-pre-line">
                {item.response.answer}
              </div>

              {/* Manual Review Required Banner */}
              {item.response.manual_review_required && (
                <div className="rounded-xl border border-amber-200 bg-amber-50/80 p-4 text-xs text-amber-900 space-y-2">
                  <div className="flex items-center gap-2 font-bold uppercase tracking-wider">
                    <AlertTriangle className="h-4 w-4 text-amber-600" />
                    <span>Manual Policy Review Required</span>
                  </div>
                  <p className="leading-relaxed text-[11px] text-amber-950">
                    This analysis is not a definitive coverage guarantee. Verify the cited policy wording manually before relying on it for hospitalization.
                  </p>
                  {item.response.warnings.length > 0 && (
                    <ul className="list-disc list-inside space-y-1 text-[11px]">
                      {item.response.warnings.map((warning, wIndex) => (
                        <li key={wIndex}>{warning}</li>
                      ))}
                    </ul>
                  )}
                  {item.response.unverified_answer && (
                    <details className="pt-1 text-[11px]">
                      <summary className="cursor-pointer font-semibold text-amber-900">
                        View raw unverified generation
                      </summary>
                      <p className="mt-1.5 whitespace-pre-line italic text-amber-800 bg-amber-100/50 p-2.5 rounded-lg border border-amber-200/60">
                        {item.response.unverified_answer}
                      </p>
                    </details>
                  )}
                </div>
              )}

              {/* Caveats and Conditions */}
              {item.response.caveats && item.response.caveats.length > 0 && (
                <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-3.5 text-xs text-slate-700 space-y-1.5">
                  <p className="font-bold uppercase tracking-wider text-slate-500 text-[10px]">
                    Policy Caveats &amp; Conditions
                  </p>
                  <ul className="space-y-1 pl-1 text-[11px]">
                    {item.response.caveats.map((caveat, cavIndex) => (
                      <li key={cavIndex} className="flex items-start gap-2">
                        <span className="text-amber-600 font-bold">•</span>
                        <span>{caveat}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Grounded Evidence Citations */}
              {item.response.citations && item.response.citations.length > 0 && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center justify-between text-xs font-bold uppercase tracking-wider text-slate-500">
                    <div className="flex items-center gap-1.5">
                      <ShieldCheck className="h-4 w-4 text-emerald-600" />
                      <span>Verbatim Policy Citations</span>
                    </div>
                    <span className="rounded-full bg-emerald-50 text-emerald-800 px-2 py-0.5 text-[10px] font-semibold border border-emerald-100">
                      {item.response.citations.length} Verified Sources
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {item.response.citations.map((cite, cIndex) => {
                      const citeKey = `${index}-${cIndex}`;
                      return (
                        <div
                          key={cIndex}
                          className="rounded-xl border border-slate-200/80 bg-white p-4 shadow-2xs space-y-2 hover:border-slate-300 transition"
                        >
                          <div className="flex items-center justify-between text-[11px]">
                            <span className="font-bold text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-md border border-emerald-100">
                              Page {cite.page_number}
                            </span>
                            <div className="flex items-center gap-2">
                              <span className="font-mono text-[10px] text-slate-400">
                                {cite.chunk_id}
                              </span>
                              <button
                                type="button"
                                onClick={() => copyCitation(cite.quote, citeKey)}
                                className="text-slate-400 hover:text-slate-700 transition"
                                title="Copy quote"
                              >
                                {copiedCitationIndex === citeKey ? (
                                  <Check className="h-3 w-3 text-emerald-600" />
                                ) : (
                                  <Copy className="h-3 w-3" />
                                )}
                              </button>
                            </div>
                          </div>
                          <p className="text-xs text-slate-700 italic border-l-2 border-emerald-500 pl-3 py-0.5 leading-relaxed">
                            &ldquo;{cite.quote}&rdquo;
                          </p>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ))
        ) : (
          /* Structured Interactive Empty State */
          <div className="rounded-2xl border border-slate-200/90 bg-white p-8 shadow-xs space-y-6">
            <div className="text-center max-w-lg mx-auto space-y-2">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 border border-emerald-100 shadow-2xs">
                <BookOpen className="h-6 w-6" />
              </div>
              <h3 className="text-lg font-bold text-slate-900">
                Grounded Policy Question Answering
              </h3>
              <p className="text-xs text-slate-600 leading-relaxed">
                Type any coverage inquiry above or select a preset prompt. Every response is verified strictly against extracted policy chunks with exact page numbers.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
              <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-1.5 text-center">
                <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-100/70 text-emerald-800 mb-1">
                  <ShieldCheck className="h-4 w-4" />
                </div>
                <h4 className="text-xs font-bold text-slate-900">Zero Hallucinations</h4>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Refuses to invent policy terms if not stated in your contract schedule.
                </p>
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-1.5 text-center">
                <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100/70 text-blue-800 mb-1">
                  <Quote className="h-4 w-4" />
                </div>
                <h4 className="text-xs font-bold text-slate-900">Verbatim Excerpts</h4>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Direct quotes with chunk IDs and page anchors for immediate validation.
                </p>
              </div>

              <div className="rounded-xl border border-slate-100 bg-slate-50/70 p-4 space-y-1.5 text-center">
                <div className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-amber-100/70 text-amber-800 mb-1">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <h4 className="text-xs font-bold text-slate-900">Caveat Detection</h4>
                <p className="text-[11px] text-slate-500 leading-relaxed">
                  Highlights sublimits, copays, and conditional clauses automatically.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
