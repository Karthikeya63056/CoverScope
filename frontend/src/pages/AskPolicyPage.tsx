import React, { useEffect, useState, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import {
  MessageSquare,
  Send,
  ShieldCheck,
  FileText,
  AlertCircle,
  HelpCircle,
  Sparkles,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RotateCcw,
  Copy,
  Check,
  BookOpen,
  ArrowRight,
  User,
  Bot,
  ChevronDown,
  ChevronUp,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Trash2,
  Calendar,
  Search,
  ArrowUp,
  ArrowDown,
  Paperclip,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { PolicySummary, AnswerResponse, ConversationSummaryItem } from '../lib/types';

interface QAMessage {
  question: string;
  response: AnswerResponse;
  timestamp: string;
}

interface LocalConversation {
  id: string;
  policy_id: string;
  policy_name?: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: QAMessage[];
}

const STORAGE_KEY = 'coverscope_chat_history_v2';

function getStoredConversations(): LocalConversation[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveStoredConversations(threads: LocalConversation[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(threads.slice(0, 100)));
  } catch {}
}

function getDateGroup(dateStr: string): string {
  if (!dateStr) return 'Recent';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const itemDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const diffDays = Math.floor((today.getTime() - itemDay.getTime()) / (1000 * 60 * 60 * 24));

    if (diffDays <= 0) return 'Today';
    if (diffDays === 1) return 'Yesterday';
    if (diffDays <= 7) return 'Previous 7 Days';
    if (diffDays <= 30) return 'Previous 30 Days';
    return 'Older';
  } catch {
    return 'Recent';
  }
}

function formatRelativeTime(dateStr: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 2) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return 'Yesterday';
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

// Custom Markdown Prose Formatter for ChatGPT / Gemini styled answers
const FormattedMarkdown: React.FC<{ content: string }> = ({ content }) => {
  if (!content) return null;

  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let currentList: string[] = [];

  const flushList = (keyPrefix: number) => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${keyPrefix}`} className="space-y-1.5 my-2 pl-4 list-disc marker:text-emerald-500">
          {currentList.map((item, idx) => (
            <li key={idx} className="leading-relaxed">
              {renderInlineStyles(item)}
            </li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  const renderInlineStyles = (text: string): React.ReactNode => {
    // Process bold (**bold**) and inline code (`code`)
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return (
          <strong key={i} className="font-semibold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        );
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return (
          <code key={i} className="font-mono bg-slate-100 text-slate-800 px-1 py-0.5 rounded text-xs">
            {part.slice(1, -1)}
          </code>
        );
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em key={i} className="italic text-slate-700">{part.slice(1, -1)}</em>;
      }
      return part;
    });
  };

  lines.forEach((line, idx) => {
    const trimmed = line.trim();

    // Check for list items
    if (trimmed.startsWith('• ') || trimmed.startsWith('* ') || trimmed.startsWith('- ')) {
      currentList.push(trimmed.slice(2));
      return;
    }

    // Flush any pending list
    flushList(idx);

    if (!trimmed) {
      elements.push(<div key={`sp-${idx}`} className="h-2" />);
      return;
    }

    if (trimmed.startsWith('### ')) {
      elements.push(
        <h4 key={`h4-${idx}`} className="text-xs font-bold text-slate-800 uppercase tracking-wider mt-3 mb-1">
          {renderInlineStyles(trimmed.slice(4))}
        </h4>
      );
      return;
    }

    if (trimmed.startsWith('## ')) {
      elements.push(
        <h3 key={`h3-${idx}`} className="text-sm font-bold text-slate-900 mt-3.5 mb-1.5 pb-1 border-b border-slate-100">
          {renderInlineStyles(trimmed.slice(3))}
        </h3>
      );
      return;
    }

    if (trimmed.startsWith('# ')) {
      elements.push(
        <h2 key={`h2-${idx}`} className="text-base font-extrabold text-slate-900 mt-4 mb-2">
          {renderInlineStyles(trimmed.slice(2))}
        </h2>
      );
      return;
    }

    elements.push(
      <p key={`p-${idx}`} className="leading-relaxed text-slate-800">
        {renderInlineStyles(trimmed)}
      </p>
    );
  });

  flushList(lines.length);

  return <div className="text-xs sm:text-sm leading-relaxed space-y-1">{elements}</div>;
};

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
  const [copiedAnswerIndex, setCopiedAnswerIndex] = useState<number | null>(null);
  const [expandedCitations, setExpandedCitations] = useState<Record<number, boolean>>({});

  // ChatGPT Sidebar State
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [conversations, setConversations] = useState<LocalConversation[]>(() => getStoredConversations());
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [conversationSearch, setConversationSearch] = useState('');
  const [isLoadingConversations, setIsLoadingConversations] = useState(false);

  const chatContainerRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Suggested conversational starter prompts
  const samplePrompts = [
    {
      title: 'Hospital Cash Deductible',
      query: 'If I am hospitalized for 1 day, will I receive the hospital cash benefit?',
      tag: 'Deductibles',
    },
    {
      title: 'Full Policy Overview',
      query: 'What does my policy cover?',
      tag: 'Overview',
    },
    {
      title: 'Policy Exclusions Summary',
      query: 'What does my policy exclude?',
      tag: 'Exclusions',
    },
    {
      title: 'Pre-Existing Disease Waiting',
      query: 'What is the waiting period for pre-existing diseases under this policy?',
      tag: 'Waiting Periods',
    },
    {
      title: 'Room Rent & ICU Limits',
      query: 'What are the room rent and ICU sublimits in this policy?',
      tag: 'Sublimits',
    },
    {
      title: 'How to Choose Insurance',
      query: 'How should I choose health insurance?',
      tag: 'Buyer Guide',
    },
  ];

  const [showScrollBottom, setShowScrollBottom] = useState(false);
  const isNearBottomRef = useRef(true);

  const handleScroll = () => {
    if (!chatContainerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = chatContainerRef.current;
    const distanceToBottom = scrollHeight - scrollTop - clientHeight;
    const nearBottom = distanceToBottom < 120;
    isNearBottomRef.current = nearBottom;
    setShowScrollBottom(!nearBottom && messages.length > 0);
  };

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth',
      });
      setShowScrollBottom(false);
      isNearBottomRef.current = true;
    }
  };

  // Auto-scroll chat container strictly when user is at the bottom
  useEffect(() => {
    if (isNearBottomRef.current || messages.length <= 1) {
      scrollToBottom();
    }
  }, [messages, isAsking]);

  // Keep window at top on mount
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, []);

  // Update question if 'q' search param changes
  useEffect(() => {
    const qParam = searchParams.get('q');
    if (qParam) {
      setQuestion(qParam);
    }
  }, [searchParams]);

  // Load available policies
  useEffect(() => {
    async function loadPolicies() {
      try {
        setIsLoadingPolicies(true);
        const res = await api.listPolicies();
        const list = res.policies || [];
        setPolicies(list);

        const paramId = searchParams.get('policy');
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

  // Sync conversation history from backend API and merge with localStorage
  const refreshConversations = async () => {
    try {
      setIsLoadingConversations(true);
      // Fetch all user conversations (ChatGPT style: shows all threads)
      const remoteList = await api.listConversations();
      const localList = getStoredConversations();

      const mergedMap = new Map<string, LocalConversation>();

      // Put existing local threads
      localList.forEach((c) => mergedMap.set(c.id, c));

      // Merge remote summaries
      (remoteList || []).forEach((rc) => {
        const existing = mergedMap.get(rc.id);
        if (existing) {
          mergedMap.set(rc.id, {
            ...existing,
            title: rc.title || existing.title,
            updated_at: rc.updated_at || existing.updated_at,
            message_count: Math.max(rc.message_count || 0, existing.message_count || 0),
          });
        } else {
          mergedMap.set(rc.id, {
            id: rc.id,
            policy_id: rc.policy_id,
            title: rc.title || 'Policy Consultation',
            created_at: rc.created_at || new Date().toISOString(),
            updated_at: rc.updated_at || new Date().toISOString(),
            message_count: rc.message_count || 0,
            messages: [],
          });
        }
      });

      const updated = Array.from(mergedMap.values()).sort(
        (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );

      setConversations(updated);
      saveStoredConversations(updated);
    } catch (err) {
      console.debug('Failed to sync remote conversations:', err);
    } finally {
      setIsLoadingConversations(false);
    }
  };

  useEffect(() => {
    refreshConversations();
  }, []);

  // Switch to a conversation thread
  const handleSelectConversation = async (conv: LocalConversation) => {
    setActiveConversationId(conv.id);
    setErrorMsg(null);

    // If the conversation was for a different policy that exists in our list, switch to it
    if (conv.policy_id && conv.policy_id !== selectedPolicyId) {
      const match = policies.find(
        (p) => (p.policy_id || p.id) === conv.policy_id || (p as any).fingerprint === conv.policy_id
      );
      if (match) {
        setSelectedPolicyId(match.policy_id || match.id || conv.policy_id);
      }
    }

    // If local conversation already has messages, load them instantly
    if (conv.messages && conv.messages.length > 0) {
      setMessages(conv.messages);
      return;
    }

    // Otherwise fetch messages from API
    try {
      setIsAsking(true);
      const hist = await api.getConversationMessages(conv.id);
      if (hist.messages && hist.messages.length > 0) {
        const restored: QAMessage[] = [];
        for (let i = 0; i < hist.messages.length; i++) {
          const m = hist.messages[i];
          if (m.role === 'user') {
            const nextMsg =
              i + 1 < hist.messages.length && hist.messages[i + 1].role === 'assistant'
                ? hist.messages[i + 1]
                : null;

            if (nextMsg) {
              const em = nextMsg.evidence_metadata || {};
              restored.push({
                question: m.content,
                timestamp: m.created_at
                  ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '',
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
            } else {
              restored.push({
                question: m.content,
                timestamp: m.created_at
                  ? new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                  : '',
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
        setMessages(restored);

        // Update local conversation messages cache
        setConversations((prev) => {
          const updated = prev.map((c) => (c.id === conv.id ? { ...c, messages: restored } : c));
          saveStoredConversations(updated);
          return updated;
        });
      } else {
        setMessages([]);
      }
    } catch (err: any) {
      console.error('Failed to load conversation messages:', err);
    } finally {
      setIsAsking(false);
    }
  };

  const handleStartNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setErrorMsg(null);
    setQuestion('');
    setTimeout(() => {
      textareaRef.current?.focus({ preventScroll: true });
    }, 50);
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    if (!window.confirm('Delete this chat thread?')) return;
    try {
      // 1. Delete locally immediately
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== convId);
        saveStoredConversations(next);
        return next;
      });
      if (activeConversationId === convId) {
        handleStartNewChat();
      }
      // 2. Delete remotely
      await api.deleteConversation(convId);
    } catch (err: any) {
      console.debug('Remote delete failed or offline:', err);
    }
  };

  const handleAsk = async (queryText?: string) => {
    const q = (queryText || question).trim();
    if (!q) return;

    if (!selectedPolicyId) {
      setErrorMsg('Please select a policy document to chat with.');
      return;
    }

    setIsAsking(true);
    setErrorMsg(null);
    setQuestion('');

    const currentDoc = policies.find((p) => (p.policy_id || p.id) === selectedPolicyId);
    const docName = currentDoc?.filename || currentDoc?.document_name || 'Policy';

    try {
      // Submit question with active conversation ID (if any)
      const res = await api.askQuestion(selectedPolicyId, q, activeConversationId || undefined);
      const convId = res.conversation_id || activeConversationId || `local-${Date.now()}`;

      if (res.conversation_id) {
        setActiveConversationId(res.conversation_id);
      }

      const newMsg: QAMessage = {
        question: q,
        response: res,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      const updatedMessages = [...messages, newMsg];
      setMessages(updatedMessages);

      // Save to localStorage immediately
      setConversations((prev) => {
        const existingIdx = prev.findIndex((c) => c.id === convId);
        let updated: LocalConversation[];

        if (existingIdx >= 0) {
          updated = [...prev];
          updated[existingIdx] = {
            ...updated[existingIdx],
            updated_at: new Date().toISOString(),
            message_count: updatedMessages.length * 2,
            messages: updatedMessages,
          };
        } else {
          const newThread: LocalConversation = {
            id: convId,
            policy_id: selectedPolicyId,
            policy_name: docName,
            title: q.slice(0, 60),
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
            message_count: updatedMessages.length * 2,
            messages: updatedMessages,
          };
          updated = [newThread, ...prev];
        }

        saveStoredConversations(updated);
        return updated;
      });

      // Background sync with MongoDB
      refreshConversations();
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to retrieve answer from policy.');
    } finally {
      setIsAsking(false);
      setTimeout(() => {
        textareaRef.current?.focus({ preventScroll: true });
      }, 50);
    }
  };

  const handleClearChat = async () => {
    if (!selectedPolicyId || messages.length === 0) return;
    if (!window.confirm('Reset this conversation?')) return;
    setErrorMsg(null);
    setMessages([]);
    if (activeConversationId) {
      try {
        await api.deleteConversation(activeConversationId);
      } catch {}
      setConversations((prev) => {
        const next = prev.filter((c) => c.id !== activeConversationId);
        saveStoredConversations(next);
        return next;
      });
      setActiveConversationId(null);
    }
  };

  const copyCitation = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCitationIndex(id);
    setTimeout(() => setCopiedCitationIndex(null), 2000);
  };

  const copyAnswer = (text: string, msgIdx: number) => {
    const msg = messages[msgIdx];
    let fullText = text;
    if (msg?.response?.caveats && msg.response.caveats.length > 0 && !isAssistantIntro(msg.response)) {
      fullText += '\n\nImportant Conditions & Caveats:\n' + msg.response.caveats.map((c) => `• ${c}`).join('\n');
    }
    navigator.clipboard.writeText(fullText);
    setCopiedAnswerIndex(msgIdx);
    setTimeout(() => setCopiedAnswerIndex(null), 2000);
  };

  const toggleCitations = (msgIndex: number) => {
    setExpandedCitations((prev) => ({
      ...prev,
      [msgIndex]: !prev[msgIndex],
    }));
  };

  // Determine if response is an assistant greeting / intro
  const isAssistantIntro = (res: AnswerResponse) => {
    const ans = (res.answer || '').toLowerCase();
    return (
      ans.includes('coverscope') &&
      (ans.includes('hello!') || ans.includes('how can i help') || ans.includes('how can i assist') || ans.includes('ai-powered'))
    );
  };

  const renderVerdictBadge = (res: AnswerResponse) => {
    if (isAssistantIntro(res)) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200 shadow-2xs">
          <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
          CoverScope Assistant
        </span>
      );
    }

    const v = (res.verdict || '').toLowerCase();
    if (v === 'covered') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100/90 px-3 py-1 text-xs font-bold text-emerald-900 border border-emerald-300 shadow-2xs">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
          Covered
        </span>
      );
    }
    if (v === 'excluded') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100/90 px-3 py-1 text-xs font-bold text-rose-900 border border-rose-300 shadow-2xs">
          <XCircle className="h-3.5 w-3.5 text-rose-600" />
          Excluded
        </span>
      );
    }
    if (v === 'depends') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100/90 px-3 py-1 text-xs font-bold text-amber-900 border border-amber-300 shadow-2xs">
          <AlertTriangle className="h-3.5 w-3.5 text-amber-600" />
          Conditional / Depends
        </span>
      );
    }
    if (v === 'summary' || v === 'overview') {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-sky-100/90 px-3 py-1 text-xs font-bold text-sky-900 border border-sky-300 shadow-2xs">
          <BookOpen className="h-3.5 w-3.5 text-sky-600" />
          Policy Summary
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700 border border-slate-300 shadow-2xs">
        <HelpCircle className="h-3.5 w-3.5 text-slate-500" />
        Not Stated in Policy
      </span>
    );
  };

  const renderVerificationBadge = (res: AnswerResponse) => {
    if (isAssistantIntro(res)) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 shadow-2xs">
          <Bot className="h-3 w-3 text-emerald-600" />
          AI Guide
        </span>
      );
    }
    // 1. Manual Review or Invalid Citations or Low Confidence -> Needs Review
    if (res.manual_review_required || !res.citations_valid || res.confidence === 'low') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-rose-50 border border-rose-200 px-2.5 py-0.5 text-[10px] font-bold text-rose-700 shadow-2xs">
          <AlertTriangle className="h-3 w-3 text-rose-500" />
          Needs Review
        </span>
      );
    }
    // 2. Active Warnings -> Partially Verified
    if (res.warnings && res.warnings.length > 0) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 shadow-2xs">
          <AlertCircle className="h-3 w-3 text-amber-600" />
          Partially Verified
        </span>
      );
    }
    // 3. Educational Guidance (General principles, not document findings)
    if (
      res.caveats &&
      res.caveats.some((c) => c.toLowerCase().includes('educational') || c.toLowerCase().includes('advisory'))
    ) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-indigo-50 border border-indigo-200 px-2.5 py-0.5 text-[10px] font-semibold text-indigo-700 shadow-2xs">
          <Sparkles className="h-3 w-3 text-indigo-500" />
          General Guidance
        </span>
      );
    }
    // 4. Policy Summary Mode: check category support depth
    const v = (res.verdict || '').toLowerCase();
    if (v === 'summary') {
      const isFull = res.confidence === 'high' && (res.citations?.length || 0) >= 4;
      if (isFull) {
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800 shadow-2xs">
            <ShieldCheck className="h-3 w-3 text-emerald-600" />
            Verified Synthesis
          </span>
        );
      }
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 shadow-2xs">
          <AlertCircle className="h-3 w-3 text-amber-600" />
          Partial Synthesis
        </span>
      );
    }
    // 5. Conditional / Depends
    if (v === 'depends') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 shadow-2xs">
          <AlertCircle className="h-3 w-3 text-amber-600" />
          Conditional / Unresolved
        </span>
      );
    }
    // 6. Not Stated in Policy (Must NOT be confused with Excluded or Verified)
    if (v === 'not_stated') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-2xs">
          <HelpCircle className="h-3 w-3 text-slate-400" />
          Unstated in Document
        </span>
      );
    }
    // 7. Full Verified Evidence (Strict: Covered / Excluded with High Confidence, Valid Citations, No Warnings)
    if (
      res.citations &&
      res.citations.length > 0 &&
      res.citations_valid &&
      !res.manual_review_required &&
      res.confidence === 'high'
    ) {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2.5 py-0.5 text-[10px] font-bold text-emerald-800 shadow-2xs">
          <ShieldCheck className="h-3 w-3 text-emerald-600" />
          Verified Evidence
        </span>
      );
    }
    // 8. Moderate confidence fallback
    if (res.confidence === 'medium') {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 border border-amber-200 px-2.5 py-0.5 text-[10px] font-bold text-amber-800 shadow-2xs">
          <AlertCircle className="h-3 w-3 text-amber-600" />
          Partially Verified
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 border border-slate-200 px-2.5 py-0.5 text-[10px] font-medium text-slate-600 shadow-2xs">
        <HelpCircle className="h-3 w-3 text-slate-400" />
        Unverified Wording
      </span>
    );
  };

  const currentPolicy = policies.find((p) => (p.policy_id || p.id) === selectedPolicyId);

  // Group conversations by date (ChatGPT style)
  const filteredConversations = conversations.filter((c) => {
    if (!conversationSearch.trim()) return true;
    const term = conversationSearch.toLowerCase();
    return (c.title || '').toLowerCase().includes(term);
  });

  const dateGroups: Record<string, LocalConversation[]> = {};
  const order = ['Today', 'Yesterday', 'Previous 7 Days', 'Previous 30 Days', 'Older'];

  filteredConversations.forEach((conv) => {
    const grp = getDateGroup(conv.updated_at || conv.created_at);
    if (!dateGroups[grp]) dateGroups[grp] = [];
    dateGroups[grp].push(conv);
  });

  return (
    <div className="flex h-full w-full overflow-hidden bg-white relative">
      {/* 1. ChatGPT-Style Left Sidebar (Dark Obsidian / Slate Theme - Completely Fixed) */}
      <aside
        className={`${
          isSidebarOpen ? 'w-64 sm:w-72' : 'w-0'
        } transition-all duration-200 ease-in-out shrink-0 bg-[#171717] text-slate-200 flex flex-col h-full overflow-hidden border-r border-slate-800 relative z-30 select-none`}
      >
        {isSidebarOpen && (
          <div className="flex flex-col h-full w-64 sm:w-72 p-3 space-y-3">
            {/* Sidebar Top: New Chat Button + Collapse */}
            <div className="flex items-center justify-between gap-2 shrink-0">
              <button
                type="button"
                onClick={handleStartNewChat}
                className="flex-1 flex items-center justify-between gap-2 rounded-xl bg-white/10 hover:bg-white/15 px-3 py-2 text-xs font-semibold text-white transition cursor-pointer border border-white/10 hover:border-white/20"
                title="Start a new chat thread"
              >
                <div className="flex items-center gap-2">
                  <Plus className="h-4 w-4 text-emerald-400" />
                  <span>New chat</span>
                </div>
                <span className="text-[10px] text-slate-400 font-mono">⌘N</span>
              </button>

              <button
                type="button"
                onClick={() => setIsSidebarOpen(false)}
                title="Close sidebar"
                className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition cursor-pointer"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            </div>

            {/* Past Chats Search Bar */}
            {conversations.length > 2 && (
              <div className="relative flex items-center shrink-0">
                <Search className="h-3.5 w-3.5 text-slate-400 absolute left-2.5 pointer-events-none" />
                <input
                  type="text"
                  value={conversationSearch}
                  onChange={(e) => setConversationSearch(e.target.value)}
                  placeholder="Search chats..."
                  className="w-full bg-white/5 border border-white/10 rounded-lg pl-8 pr-2.5 py-1.5 text-xs text-white placeholder:text-slate-500 focus:outline-hidden focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
                />
              </div>
            )}

            {/* Scrollable Conversation Threads Grouped By Date */}
            <div className="flex-1 overflow-y-auto space-y-4 pr-1 scrollbar-thin scrollbar-thumb-slate-700">
              {isLoadingConversations && conversations.length === 0 ? (
                <div className="space-y-2 py-2">
                  <div className="h-8 rounded-lg bg-white/5 animate-pulse" />
                  <div className="h-8 rounded-lg bg-white/5 animate-pulse" />
                  <div className="h-8 rounded-lg bg-white/5 animate-pulse" />
                </div>
              ) : filteredConversations.length === 0 ? (
                <div className="py-12 px-3 text-center text-xs text-slate-400 space-y-2">
                  <MessageSquare className="h-6 w-6 text-slate-600 mx-auto" />
                  <p>No past chats found.</p>
                  <button
                    type="button"
                    onClick={handleStartNewChat}
                    className="text-[11px] font-semibold text-emerald-400 hover:underline cursor-pointer"
                  >
                    Start a new chat &rarr;
                  </button>
                </div>
              ) : (
                order.map((groupTitle) => {
                  const items = dateGroups[groupTitle];
                  if (!items || items.length === 0) return null;

                  return (
                    <div key={groupTitle} className="space-y-1">
                      <div className="px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-400">
                        {groupTitle}
                      </div>
                      {items.map((conv) => {
                        const isActive = activeConversationId === conv.id;
                        return (
                          <div
                            key={conv.id}
                            onClick={() => handleSelectConversation(conv)}
                            className={`group relative flex items-center justify-between rounded-lg px-2.5 py-2 text-left text-xs transition cursor-pointer ${
                              isActive
                                ? 'bg-white/15 text-white font-medium border-l-2 border-emerald-400 shadow-2xs'
                                : 'text-slate-300 hover:bg-white/10 hover:text-white'
                            }`}
                          >
                            <div className="flex items-center gap-2 min-w-0 flex-1">
                              <MessageSquare
                                className={`h-3.5 w-3.5 shrink-0 ${
                                  isActive ? 'text-emerald-400' : 'text-slate-500'
                                }`}
                              />
                              <div className="min-w-0 flex-1 truncate">
                                <span className="truncate block leading-snug">
                                  {conv.title || 'Policy Consultation'}
                                </span>
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={(e) => handleDeleteConversation(e, conv.id)}
                              title="Delete conversation"
                              className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-rose-400 transition p-1 rounded-sm hover:bg-white/10 cursor-pointer ml-1"
                            >
                              <Trash2 className="h-3 w-3" />
                            </button>
                          </div>
                        );
                      })}
                    </div>
                  );
                })
              )}
            </div>

            {/* Sidebar Bottom: Model / Grounding Badge */}
            <div className="pt-2 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="font-medium text-slate-300">CoverScope QA</span>
              </div>
              <span className="text-[10px] font-mono text-slate-500">Groq OSS-120B</span>
            </div>
          </div>
        )}
      </aside>

      {/* 2. Main Chat Area (ChatGPT / Gemini Minimalist Center Stream) */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-white relative">
        {/* Sleek Top Navigation Bar */}
        <header className="flex items-center justify-between gap-3 bg-white border-b border-slate-100 px-4 py-2 shrink-0 z-20 h-12">
          <div className="flex items-center gap-2.5 min-w-0">
            {!isSidebarOpen && (
              <button
                type="button"
                onClick={() => setIsSidebarOpen(true)}
                title="Open conversation sidebar"
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white hover:bg-slate-100 text-slate-700 transition cursor-pointer"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            )}

            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-600 text-white shadow-xs shrink-0">
              <Sparkles className="h-3.5 w-3.5" />
            </div>

            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h1 className="text-sm font-bold text-slate-900 truncate">Ask My Policy</h1>
                <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 border border-emerald-200 px-2 py-0.2 text-[10px] font-semibold text-emerald-800">
                  <ShieldCheck className="h-2.5 w-2.5 text-emerald-600" />
                  Grounded
                </span>
              </div>
            </div>
          </div>

          {/* Right Controls: Policy Selector & Reset */}
          <div className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1 text-xs">
              <FileText className="h-3.5 w-3.5 text-emerald-600 shrink-0" />
              {isLoadingPolicies ? (
                <span className="h-4 w-20 animate-pulse rounded bg-slate-200 inline-block" />
              ) : policies.length > 0 ? (
                <select
                  id="target-policy-qa"
                  aria-label="Active Policy Document"
                  value={selectedPolicyId}
                  onChange={(e) => setSelectedPolicyId(e.target.value)}
                  className="bg-transparent font-medium text-slate-800 text-xs focus:outline-hidden cursor-pointer max-w-[160px] sm:max-w-[220px] truncate"
                >
                  {policies.map((p) => {
                    const id = p.policy_id || p.id || '';
                    const name = p.filename || p.document_name || 'Policy Document';
                    return (
                      <option key={id} value={id}>
                        {name} ({p.page_count ?? 1}p)
                      </option>
                    );
                  })}
                </select>
              ) : (
                <Link to="/library" className="text-xs font-semibold text-emerald-700 hover:underline">
                  Upload &rarr;
                </Link>
              )}
            </div>

            <button
              type="button"
              onClick={handleStartNewChat}
              title="Start a new chat thread"
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 text-slate-700 px-2.5 py-1 text-xs font-medium transition cursor-pointer"
            >
              <Plus className="h-3.5 w-3.5 text-emerald-600" />
              <span className="hidden sm:inline">New</span>
            </button>

            {messages.length > 0 && (
              <button
                type="button"
                onClick={handleClearChat}
                title="Reset conversation"
                className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs font-medium text-slate-500 hover:bg-slate-50 hover:text-slate-800 transition cursor-pointer"
              >
                <RotateCcw className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
        </header>

        {/* Error notification banner */}
        {errorMsg && (
          <div className="mx-4 mt-2 flex items-start gap-2.5 rounded-xl border border-rose-200 bg-rose-50 p-2.5 text-xs text-rose-800 shadow-2xs shrink-0">
            <AlertCircle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
            <span className="flex-1">{errorMsg}</span>
            <button
              onClick={() => setErrorMsg(null)}
              className="text-rose-500 hover:text-rose-800 font-bold ml-1 text-sm leading-none"
            >
              &times;
            </button>
          </div>
        )}

        {/* Scrollable Chat Feed (Spans full height of the main panel with roomy bottom padding) */}
        <div
          ref={chatContainerRef}
          onScroll={handleScroll}
          className="flex-1 overflow-y-auto overflow-x-hidden p-4 sm:p-6 scrollbar-thin scrollbar-thumb-slate-200 hover:scrollbar-thumb-slate-300 relative"
        >
          <div className="max-w-3xl mx-auto w-full space-y-6 pb-40">
            {messages.length === 0 ? (
              /* Hero Empty State */
              <div className="flex flex-col items-center justify-center min-h-[360px] text-center max-w-xl mx-auto space-y-6 py-8">
                <div className="relative">
                  <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-600 text-white shadow-lg shadow-emerald-600/20">
                    <Sparkles className="h-8 w-8" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 flex h-6 w-6 items-center justify-center rounded-full bg-emerald-100 text-emerald-800 border-2 border-white">
                    <ShieldCheck className="h-3.5 w-3.5 text-emerald-700" />
                  </div>
                </div>

                <div className="space-y-2">
                  <h2 className="text-xl sm:text-2xl font-extrabold tracking-tight text-slate-900">
                    How can I help you today?
                  </h2>
                  <p className="text-xs sm:text-sm text-slate-500 max-w-md mx-auto leading-relaxed">
                    Ask coverage questions, check waiting periods, room rent sublimits, or exclusions.
                    Answers are strictly cross-verified against{' '}
                    <strong className="text-slate-700">
                      {currentPolicy?.filename || 'your uploaded policy'}
                    </strong>
                    .
                  </p>
                </div>

                {/* Quick Inquiries Grid */}
                <div className="w-full pt-2">
                  <p className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-3 text-left">
                    Suggested queries:
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-left">
                    {samplePrompts.map((preset, i) => (
                      <button
                        key={i}
                        type="button"
                        onClick={() => handleAsk(preset.query)}
                        className="flex flex-col justify-between p-3.5 rounded-xl border border-slate-200 bg-white hover:border-emerald-500 hover:bg-emerald-50/20 hover:shadow-xs transition-all text-left group cursor-pointer"
                      >
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md">
                            {preset.tag}
                          </span>
                          <ArrowRight className="h-3 w-3 text-slate-300 group-hover:text-emerald-600 group-hover:translate-x-0.5 transition-all" />
                        </div>
                        <span className="text-xs font-semibold text-slate-800 group-hover:text-emerald-950 leading-snug">
                          {preset.title}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              /* Conversational Messages */
              messages.map((item, index) => {
                const hasCitations = item.response.citations && item.response.citations.length > 0;
                const isCitationsOpen = expandedCitations[index] ?? true;
                const introMode = isAssistantIntro(item.response);

                return (
                  <div key={index} className="space-y-4">
                    {/* User Query Bubble (Right-aligned ChatGPT Pill) */}
                    <div className="flex items-start justify-end gap-2.5">
                      <div className="flex flex-col items-end max-w-[85%] sm:max-w-[75%] space-y-1">
                        <div className="rounded-2xl rounded-tr-xs bg-slate-900 text-white px-4 py-2.5 text-sm font-medium shadow-xs leading-relaxed">
                          {item.question}
                        </div>
                        <span className="text-[10px] text-slate-400 px-1">{item.timestamp}</span>
                      </div>
                      <div className="flex h-7 w-7 items-center justify-center rounded-full bg-slate-200 text-slate-700 shrink-0 mt-0.5 shadow-2xs">
                        <User className="h-3.5 w-3.5" />
                      </div>
                    </div>

                    {/* Assistant Response Card (Left-aligned ChatGPT / Gemini Prose Card) */}
                    <div className="flex items-start gap-3">
                      <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-600 text-white shrink-0 mt-1 shadow-xs">
                        <Bot className="h-4 w-4" />
                      </div>

                      <div className="flex-1 max-w-[95%] sm:max-w-[92%] rounded-2xl rounded-tl-xs border border-slate-200/90 bg-white p-4 sm:p-5 shadow-xs space-y-3.5">
                        {/* Header Status Row: Verdict, Verification & Copy */}
                        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2.5">
                          <div className="flex items-center gap-2">
                            {renderVerdictBadge(item.response)}
                            {renderVerificationBadge(item.response)}
                          </div>

                          <button
                            type="button"
                            onClick={() => copyAnswer(item.response.answer, index)}
                            title="Copy response text"
                            className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-700 transition px-2 py-1 rounded-md hover:bg-slate-100 cursor-pointer"
                          >
                            {copiedAnswerIndex === index ? (
                              <>
                                <Check className="h-3.5 w-3.5 text-emerald-600" />
                                <span className="text-emerald-700 font-medium">Copied</span>
                              </>
                            ) : (
                              <>
                                <Copy className="h-3.5 w-3.5" />
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                        </div>

                        {/* Answer Markdown Prose */}
                        <FormattedMarkdown content={item.response.answer} />

                        {/* Caveats Notice (only if non-empty and not intro mode) */}
                        {!introMode && item.response.caveats && item.response.caveats.length > 0 && (
                          <div className="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3 text-xs text-amber-900 space-y-1.5">
                            <div className="flex items-center gap-1.5 font-bold uppercase tracking-wider text-amber-800 text-[10px]">
                              <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0" />
                              <span>Important Conditions &amp; Caveats</span>
                            </div>
                            <ul className="space-y-1 text-[11px] text-amber-950 pl-1">
                              {item.response.caveats.map((c, cavIdx) => (
                                <li key={cavIdx} className="flex items-start gap-1.5 leading-snug">
                                  <span className="text-amber-600 font-bold shrink-0">&bull;</span>
                                  <span>{c}</span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Verbatim Citations Collapsible Shelf */}
                        {hasCitations && (
                          <div className="pt-2 border-t border-slate-100">
                            <button
                              type="button"
                              onClick={() => toggleCitations(index)}
                              className="flex items-center justify-between w-full text-xs font-semibold text-slate-600 hover:text-emerald-700 py-1 cursor-pointer"
                            >
                              <div className="flex items-center gap-1.5">
                                <ShieldCheck className="h-4 w-4 text-emerald-600" />
                                <span>Verbatim Evidence Citations ({item.response.citations.length})</span>
                              </div>
                              <div className="flex items-center gap-1 text-[11px] text-slate-400">
                                <span>{isCitationsOpen ? 'Hide' : 'Show'}</span>
                                {isCitationsOpen ? (
                                  <ChevronUp className="h-3.5 w-3.5" />
                                ) : (
                                  <ChevronDown className="h-3.5 w-3.5" />
                                )}
                              </div>
                            </button>

                            {isCitationsOpen && (
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 pt-2 animate-in fade-in-50 duration-150">
                                {item.response.citations.map((cite, cIdx) => {
                                  const citeKey = `${index}-${cIdx}`;
                                  return (
                                    <div
                                      key={cIdx}
                                      className="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 text-xs space-y-1.5 hover:border-slate-300 transition"
                                    >
                                      <div className="flex items-center justify-between">
                                        <span className="font-bold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded text-[10px] border border-emerald-200/60">
                                          Page {cite.page_number}
                                        </span>
                                        <div className="flex items-center gap-1.5">
                                          <span className="font-mono text-[9px] text-slate-400">
                                            {cite.chunk_id}
                                          </span>
                                          <button
                                            type="button"
                                            onClick={() => copyCitation(cite.quote, citeKey)}
                                            className="text-slate-400 hover:text-slate-700 transition p-0.5 rounded cursor-pointer"
                                            title="Copy exact quote"
                                          >
                                            {copiedCitationIndex === citeKey ? (
                                              <Check className="h-3 w-3 text-emerald-600" />
                                            ) : (
                                              <Copy className="h-3 w-3" />
                                            )}
                                          </button>
                                        </div>
                                      </div>
                                      <p className="text-[11px] text-slate-700 italic border-l-2 border-emerald-500 pl-2.5 py-0.5 leading-relaxed">
                                        &ldquo;{cite.quote}&rdquo;
                                      </p>
                                    </div>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}

            {/* Live Thinking Indicator Bubble */}
            {isAsking && (
              <div className="flex items-start gap-3 animate-in fade-in-50 duration-150">
                <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-emerald-600 text-white shrink-0 mt-1 shadow-xs">
                  <Bot className="h-4 w-4" />
                </div>
                <div className="rounded-2xl rounded-tl-xs border border-slate-200 bg-white p-4 shadow-xs space-y-2 max-w-[85%]">
                  <div className="flex items-center gap-2 text-xs font-semibold text-emerald-800">
                    <Sparkles className="h-3.5 w-3.5 text-emerald-600 animate-spin" />
                    <span>Searching policy text &amp; verifying clauses...</span>
                  </div>
                  <div className="flex items-center gap-1.5 pt-1">
                    <span
                      className="h-2 w-2 rounded-full bg-emerald-500 animate-bounce"
                      style={{ animationDelay: '0ms' }}
                    />
                    <span
                      className="h-2 w-2 rounded-full bg-emerald-500 animate-bounce"
                      style={{ animationDelay: '150ms' }}
                    />
                    <span
                      className="h-2 w-2 rounded-full bg-emerald-500 animate-bounce"
                      style={{ animationDelay: '300ms' }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Floating Scroll-to-Bottom Jump Button */}
        {showScrollBottom && (
          <button
            type="button"
            onClick={scrollToBottom}
            title="Jump to latest message"
            className="absolute bottom-36 right-6 sm:right-1/2 sm:translate-x-56 z-30 flex h-9 w-9 items-center justify-center rounded-full bg-white border border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-50 shadow-md hover:shadow-lg transition-all cursor-pointer animate-in fade-in zoom-in-75 duration-150"
          >
            <ArrowDown className="h-4 w-4" />
          </button>
        )}

        {/* 3. Floating Bottom Dock Bar (ChatGPT / Gemini Signature Floating Input) */}
        <div className="absolute bottom-0 left-0 right-0 z-20 pointer-events-none bg-gradient-to-t from-white via-white/95 to-transparent pt-8 pb-3 px-4">
          <div className="max-w-3xl mx-auto w-full pointer-events-auto space-y-2">
            {/* Follow-up question suggestion chips */}
            {messages.length > 0 && (
              <div className="flex items-center gap-1.5 overflow-x-auto pb-1 scrollbar-none text-xs">
                <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider shrink-0 mr-1">
                  Suggested:
                </span>
                {samplePrompts.slice(0, 4).map((p, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => handleAsk(p.query)}
                    className="rounded-full bg-white/95 backdrop-blur-xs border border-slate-200 px-3 py-1 text-slate-600 hover:border-emerald-500 hover:text-emerald-800 hover:bg-emerald-50/50 whitespace-nowrap transition shadow-2xs cursor-pointer text-[11px]"
                  >
                    + {p.title}
                  </button>
                ))}
              </div>
            )}

            {/* ChatGPT Centered Input Capsule */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleAsk();
              }}
              className="relative flex flex-col bg-white border border-slate-300 rounded-2xl shadow-sm focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 transition-all p-2 gap-1.5"
            >
              {/* Active Policy Context Pill inside dock */}
              <div className="flex items-center justify-between px-2 pt-0.5 text-[11px] text-slate-400">
                <div className="flex items-center gap-1 text-emerald-800 font-medium">
                  <Paperclip className="h-3 w-3 text-emerald-600" />
                  <span className="truncate max-w-[280px]">
                    {currentPolicy?.filename || 'No policy attached'}
                  </span>
                  {currentPolicy?.page_count && (
                    <span className="text-slate-400 font-normal">({currentPolicy.page_count}p)</span>
                  )}
                </div>
                <span className="text-[10px] text-slate-400 hidden sm:inline">
                  Press Enter to send, Shift+Enter for newline
                </span>
              </div>

              <div className="flex items-end gap-2">
                <textarea
                  ref={textareaRef}
                  rows={1}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder="Ask anything about this policy..."
                  className="w-full resize-none bg-transparent px-2.5 py-1.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-hidden max-h-32 leading-relaxed"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleAsk();
                    }
                  }}
                />

                <button
                  type="submit"
                  disabled={isAsking || !question.trim() || !selectedPolicyId}
                  className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-900 text-white shadow-xs hover:bg-emerald-600 disabled:opacity-30 disabled:hover:bg-slate-900 transition shrink-0 cursor-pointer"
                  title="Send question"
                >
                  <ArrowUp className="h-4 w-4" />
                </button>
              </div>
            </form>

            <p className="text-center text-[10px] text-slate-400 pt-0.5 select-none">
              CoverScope verifies clauses against extracted policy text. Always review official schedules for final claim decisions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
