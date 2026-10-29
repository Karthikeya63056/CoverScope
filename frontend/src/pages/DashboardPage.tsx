import React, { useEffect, useState, useLayoutEffect, useRef, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

gsap.registerPlugin(ScrollTrigger);
import {
  FileText,
  MessageSquare,
  ShieldCheck,
  ArrowRight,
  Upload,
  Scale,
  GitCompare,
  Sparkles,
  Database,
  ClipboardCheck,
  CheckCircle2,
  AlertTriangle,
  ExternalLink,
  Trash2,
  Download,
  Search,
  FileCheck,
  Clock,
  Zap,
  FileCode,
  FileSpreadsheet,
  Check,
  HelpCircle,
  ChevronRight,
  Shield,
  Layers,
} from 'lucide-react';
import { api } from '../lib/api-client';
import type { DashboardSummaryResponse, PolicySummary, PolicyFactItem } from '../lib/types';
import { useAuth } from '../context/AuthContext';
import { CardTilt } from '../components/CardTilt';

// ============================================================================
// Animated Number Counter Component (GSAP-powered, reduced-motion safe)
// ============================================================================
const AnimatedCounter: React.FC<{ value: number; duration?: number }> = ({
  value,
  duration = 0.8,
}) => {
  const [displayValue, setDisplayValue] = useState(0);
  const countRef = useRef({ val: 0 });

  useEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      setDisplayValue(value);
      return;
    }

    const obj = countRef.current;
    const tween = gsap.to(obj, {
      val: value,
      duration,
      ease: 'power2.out',
      onUpdate: () => {
        setDisplayValue(Math.round(obj.val));
      },
    });

    return () => {
      tween.kill();
    };
  }, [value, duration]);

  return <span>{displayValue}</span>;
};

// ============================================================================
// Data Models for Interactive Evidence Studio
// ============================================================================

interface EvidenceItem {
  id: string;
  tabLabel: string;
  category: string;
  sourceLabel: string;
  pageCitation: string;
  excerpt: string;
  verdictType: 'waiting' | 'copay' | 'covered' | 'sublimit';
  verdictLabel: string;
  practicalImpact: string;
  actionRoute: string;
  actionLabel: string;
  isRealExtractedFact: boolean;
}

// Fallback illustrative examples clearly labelled if no policy facts have been extracted
const ILLUSTRATIVE_BENCHMARKS: EvidenceItem[] = [
  {
    id: 'ped-waiting',
    tabLabel: 'Pre-Existing Waiting Period',
    category: 'Waiting Period',
    sourceLabel: 'Star Comprehensive Schedule — Section 6.1',
    pageCitation: 'Page 12, Clause 1',
    excerpt:
      'Pre-existing disease waiting period of 36 months applies from policy inception. Declared pre-existing conditions require continuous uninterrupted renewal before full claim admissibility.',
    verdictType: 'waiting',
    verdictLabel: '36-Month Waiting Window',
    practicalImpact:
      'Any hospitalization arising from declared hypertension, diabetes, or related complications is subject to a 36-month waiting period before expenses are admissible.',
    actionRoute: '/scenarios',
    actionLabel: 'Test in Scenario Analyzer',
    isRealExtractedFact: false,
  },
  {
    id: 'copay-deductible',
    tabLabel: 'Mandatory Co-Payment',
    category: 'Co-Payment & Deductible',
    sourceLabel: 'Star Comprehensive Schedule — Section 4.1',
    pageCitation: 'Page 4, Clause 3',
    excerpt:
      'A co-payment of 10% applies to each and every claim for insured persons aged above 60 years at the time of hospitalization, unless optional co-pay waiver rider is active.',
    verdictType: 'copay',
    verdictLabel: '10% Out-Of-Pocket Co-Pay',
    practicalImpact:
      'The insurer settles 90% of admissible expenses; the remaining 10% must be borne directly by the policyholder as out-of-pocket payment.',
    actionRoute: '/claim-rehearsal',
    actionLabel: 'Rehearse in Claim Rehearsal',
    isRealExtractedFact: false,
  },
  {
    id: 'modern-surgery',
    tabLabel: 'Modern & Robotic Surgery',
    category: 'Technology & Day-Care',
    sourceLabel: 'Star Comprehensive Schedule — Section 4.2',
    pageCitation: 'Page 14, Clause 2',
    excerpt:
      'Expenses incurred for modern treatment methods such as Robotic surgeries and Deep Brain Stimulation shall be payable up to the Sum Insured without sub-limit, subject to medical necessity.',
    verdictType: 'covered',
    verdictLabel: 'Covered Up to Sum Insured',
    practicalImpact:
      'Unlike older policies that imposed an arbitrary ₹1,00,000 sub-limit on robotic procedures, modern schedules cover approved surgeries up to the full policy limit.',
    actionRoute: '/ask?q=Is%20robotic%20surgery%20covered%20up%20to%20full%20sum%20insured%3F',
    actionLabel: 'Ask Policy About Robotic Cover',
    isRealExtractedFact: false,
  },
];

export const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const navigate = useNavigate();

  // State
  const [data, setData] = useState<DashboardSummaryResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [realFacts, setRealFacts] = useState<PolicyFactItem[]>([]);
  const [activeEvidenceIndex, setActiveEvidenceIndex] = useState(0);
  const [directQuery, setDirectQuery] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  // Animation Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const activeBarRef = useRef<HTMLDivElement>(null);
  const badgeTopRef = useRef<HTMLDivElement>(null);
  const badgeBottomRef = useRef<HTMLDivElement>(null);
  const badgeLeftRef = useRef<HTMLDivElement>(null);
  const evidenceCardRef = useRef<HTMLDivElement>(null);

  // Time-aware greeting
  const greeting = useMemo(() => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 17) return 'Good afternoon';
    return 'Good evening';
  }, []);

  // Primary active policy in focus
  const primaryPolicy = useMemo(() => {
    if (!data?.recent_policies || data.recent_policies.length === 0) return null;
    return data.recent_policies[0];
  }, [data?.recent_policies]);

  const primaryPolicyId = primaryPolicy?.policy_id || primaryPolicy?.id || '';

  // Load summary and real extracted facts
  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        setIsLoading(true);
        const res = await api.getDashboardSummary();
        if (!isMounted) return;
        setData(res);
        setIsLoading(false); // Unblock immediate rendering of active policy & shelf

        // Fetch real extracted policy facts in background if a policy is loaded
        if (res.recent_policies && res.recent_policies.length > 0) {
          const pid = res.recent_policies[0].policy_id || res.recent_policies[0].id;
          if (pid) {
            try {
              const factsRes = await api.getPolicyFacts(pid);
              if (isMounted && factsRes.facts && factsRes.facts.length > 0) {
                setRealFacts(factsRes.facts);
              }
            } catch (factsErr) {
              console.debug('Could not load policy facts:', factsErr);
            }
          }
        }
      } catch (err) {
        console.warn('Failed to load dashboard data:', err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    loadData();

    return () => {
      isMounted = false;
    };
  }, []);

  // Transform real extracted facts into Evidence Items, or fallback to standard illustrative benchmarks
  const evidenceItems: EvidenceItem[] = useMemo(() => {
    if (realFacts.length > 0) {
      return realFacts.slice(0, 4).map((f, i) => {
        const isWaiting = f.category === 'waiting_period';
        const isCopay = f.category === 'deductible_or_copay';
        const isSublimit = f.category === 'room_rent_or_icu';

        const verdictType: 'waiting' | 'copay' | 'covered' | 'sublimit' = isWaiting
          ? 'waiting'
          : isCopay
          ? 'copay'
          : isSublimit
          ? 'sublimit'
          : 'covered';

        const verdictLabel = isWaiting
          ? 'Active Waiting Period'
          : isCopay
          ? 'Mandatory Co-Payment'
          : isSublimit
          ? 'Room Rent Sub-Limit'
          : 'Extracted Policy Fact';

        const categoryLabel = f.category.replace(/_/g, ' ').toUpperCase();

        const tabLabel = isWaiting
          ? f.text.toLowerCase().includes('pre-existing')
            ? 'Pre-Existing Waiting Period'
            : f.text.toLowerCase().includes('initial')
            ? 'Initial 30-Day Waiting Period'
            : f.text.toLowerCase().includes('bariatric')
            ? 'Bariatric Waiting Period'
            : 'Specific Disease Waiting'
          : isCopay
          ? 'Co-Payment & Deductible'
          : isSublimit
          ? 'Room Rent Limits'
          : `Extracted Fact ${i + 1}`;

        return {
          id: `fact-${i}`,
          tabLabel,
          category: categoryLabel,
          sourceLabel: primaryPolicy?.filename || 'Active Policy Schedule',
          pageCitation: `Page ${f.page_number}`,
          excerpt: f.text,
          verdictType,
          verdictLabel,
          practicalImpact: isWaiting
            ? `Hospitalization expenses related to this clause are subject to mandatory duration requirements from policy inception before coverage activates.`
            : isCopay
            ? `Policyholder is responsible for the stated percentage as an out-of-pocket deduction upon hospital discharge.`
            : `Verified factual statement extracted and indexed from page ${f.page_number} of your policy schedule.`,
          actionRoute: isWaiting ? '/scenarios' : '/claim-rehearsal',
          actionLabel: isWaiting ? 'Simulate in Scenario Analyzer' : 'Rehearse in Claim Rehearsal',
          isRealExtractedFact: true,
        };
      });
    }

    return ILLUSTRATIVE_BENCHMARKS;
  }, [realFacts, primaryPolicy]);

  const activeEvidence = evidenceItems[activeEvidenceIndex] || evidenceItems[0];

  // Choreographed Master Entrance with GSAP (runs once data is present, reduced-motion safe)
  useLayoutEffect(() => {
    if (isLoading || !containerRef.current) return;

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (prefersReducedMotion) {
      gsap.set(
        [
          '.dash-header',
          '.dash-active-bar',
          '.hero-float-badge',
          '.dash-suite-header',
          '.dash-flagship-card',
          '.dash-engine-card',
          '.dash-studio',
          '.dash-shelf',
        ],
        { opacity: 1, y: 0, scale: 1, clearProps: 'all' }
      );
      return;
    }

    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: 'power3.out' } });

      tl.fromTo(
        '.dash-header',
        { opacity: 0, y: -20 },
        { opacity: 1, y: 0, duration: 0.55, ease: 'power2.out' }
      )
        .fromTo(
          '.dash-active-bar',
          { opacity: 0, y: 28, scale: 0.97 },
          { opacity: 1, y: 0, scale: 1, duration: 0.65, ease: 'power3.out' },
          '-=0.35'
        )
        .fromTo(
          '.hero-float-badge',
          { opacity: 0, scale: 0.7, y: 12 },
          { opacity: 1, scale: 1, y: 0, duration: 0.55, stagger: 0.1, ease: 'back.out(1.8)' },
          '-=0.35'
        )
        .fromTo(
          '.dash-suite-header',
          { opacity: 0, y: 18 },
          { opacity: 1, y: 0, duration: 0.5 },
          '-=0.3'
        )
        .fromTo(
          '.dash-flagship-card',
          { opacity: 0, y: 24, scale: 0.98 },
          { opacity: 1, y: 0, scale: 1, duration: 0.55, ease: 'power2.out' },
          '-=0.35'
        )
        .fromTo(
          '.dash-engine-card',
          { opacity: 0, y: 24 },
          { opacity: 1, y: 0, duration: 0.5, stagger: 0.08, ease: 'power2.out' },
          '-=0.35'
        )
        .fromTo(
          '.dash-studio',
          { opacity: 0, y: 24 },
          { opacity: 1, y: 0, duration: 0.55, ease: 'power2.out' },
          '-=0.25'
        )
        .fromTo(
          '.dash-shelf',
          { opacity: 0, y: 24 },
          { opacity: 1, y: 0, duration: 0.55, ease: 'power2.out' },
          '-=0.35'
        );

      // ScrollTrigger for Lower Operations Dock
      gsap.utils.toArray<HTMLElement>('.reveal-on-scroll').forEach((elem) => {
        gsap.fromTo(
          elem,
          { y: 30, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.7,
            ease: 'power3.out',
            scrollTrigger: {
              trigger: elem,
              start: 'top 88%',
              toggleActions: 'play none none none',
            },
          }
        );
      });
    }, containerRef);

    return () => ctx.revert();
  }, [isLoading]);

  // Pointer-driven parallax for the signature active focus bar (desktop mouse only)
  const handleActiveBarMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (
      !activeBarRef.current ||
      !window.matchMedia('(pointer: fine)').matches ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
      return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    gsap.to(activeBarRef.current, {
      rotateY: x * 6,
      rotateX: -y * 6,
      transformPerspective: 1000,
      ease: 'power1.out',
      duration: 0.35,
    });

    if (badgeTopRef.current) {
      gsap.to(badgeTopRef.current, {
        x: x * 16,
        y: y * 16,
        ease: 'power1.out',
        duration: 0.35,
      });
    }
    if (badgeBottomRef.current) {
      gsap.to(badgeBottomRef.current, {
        x: -x * 14,
        y: -y * 14,
        ease: 'power1.out',
        duration: 0.35,
      });
    }
    if (badgeLeftRef.current) {
      gsap.to(badgeLeftRef.current, {
        x: -x * 12,
        y: y * 12,
        ease: 'power1.out',
        duration: 0.35,
      });
    }
  };

  const handleActiveBarMouseLeave = () => {
    if (!activeBarRef.current) return;
    gsap.to(activeBarRef.current, {
      rotateX: 0,
      rotateY: 0,
      ease: 'power2.out',
      duration: 0.45,
    });
    if (badgeTopRef.current) {
      gsap.to(badgeTopRef.current, { x: 0, y: 0, ease: 'power2.out', duration: 0.45 });
    }
    if (badgeBottomRef.current) {
      gsap.to(badgeBottomRef.current, { x: 0, y: 0, ease: 'power2.out', duration: 0.45 });
    }
    if (badgeLeftRef.current) {
      gsap.to(badgeLeftRef.current, { x: 0, y: 0, ease: 'power2.out', duration: 0.45 });
    }
  };

  // Tab switch micro-interaction on the Evidence Studio card
  const handleSelectEvidence = (idx: number) => {
    if (idx === activeEvidenceIndex) return;
    const card = evidenceCardRef.current;
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (!card || prefersReducedMotion) {
      setActiveEvidenceIndex(idx);
      return;
    }

    gsap.to(card, {
      opacity: 0.35,
      y: 3,
      duration: 0.1,
      ease: 'power1.in',
      onComplete: () => {
        setActiveEvidenceIndex(idx);
        gsap.to(card, {
          opacity: 1,
          y: 0,
          duration: 0.18,
          ease: 'power2.out',
        });
      },
    });
  };

  // Handle direct inquiry submission
  const handleDirectQuerySubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = directQuery.trim();
    if (!q) return;
    const targetUrl = primaryPolicyId
      ? `/ask?policy=${encodeURIComponent(primaryPolicyId)}&q=${encodeURIComponent(q)}`
      : `/ask?q=${encodeURIComponent(q)}`;
    navigate(targetUrl);
  };

  // Handle policy deletion
  const handleDeletePolicy = async (id: string, name: string) => {
    if (
      !window.confirm(
        `Permanently delete policy "${name}" from your MongoDB database and storage?\n\nThis will purge the file, indexed chunks, and analysis records. This cannot be undone.`
      )
    ) {
      return;
    }
    try {
      setDeletingId(id);
      await api.deletePolicy(id);
      if (data) {
        setData({
          ...data,
          total_policies: Math.max(0, data.total_policies - 1),
          recent_policies: data.recent_policies.filter(
            (p) => (p.policy_id || p.id) !== id && p.id !== id
          ),
        });
      }
    } catch (err: any) {
      alert(err.message || 'Failed to delete policy.');
    } finally {
      setDeletingId(null);
    }
  };

  // Handle PDF download
  const handleDownloadPolicy = async (id: string, name: string) => {
    try {
      setDownloadingId(id);
      const blob = await api.downloadPolicy(id);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = name.endsWith('.pdf') ? name : `${name}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err: any) {
      alert(err.message || 'Failed to download policy PDF.');
    } finally {
      setDownloadingId(null);
    }
  };

  // Filtered policies list for the documents shelf
  const filteredPolicies = useMemo(() => {
    if (!data?.recent_policies) return [];
    if (!searchTerm.trim()) return data.recent_policies;
    const term = searchTerm.toLowerCase();
    return data.recent_policies.filter((p) => {
      const name = (p.filename || p.document_name || '').toLowerCase();
      const status = (p.status || p.processing_status || '').toLowerCase();
      return name.includes(term) || status.includes(term);
    });
  }, [data?.recent_policies, searchTerm]);

  const displayName = user?.display_name || user?.email?.split('@')[0] || '';

  return (
    <div ref={containerRef} className="relative space-y-6 pb-12">
      {/* ===================================================================== */}
      {/* ATMOSPHERIC AMBIENT GLOW BACKDROP (LANDING PAGE PARITY)               */}
      {/* ===================================================================== */}
      <div
        className="pointer-events-none absolute top-4 left-1/2 -translate-x-1/2 h-[750px] w-full max-w-7xl -z-10 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute top-10 right-1/4 h-96 w-96 rounded-full bg-teal-200/20 blur-3xl animate-glow-shift" />
        <div className="absolute top-24 left-1/3 h-80 w-80 rounded-full bg-emerald-200/20 blur-3xl animate-pulse-ambient" />
      </div>

      {/* ===================================================================== */}
      {/* 1. EDITORIAL COMMAND HEADER                                           */}
      {/* ===================================================================== */}
      <div className="dash-header flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200/90 pb-5">
        <div>
          <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
            <span className="flex h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Policy Intelligence Command</span>
            <span>•</span>
            <span className="text-slate-600 font-semibold">Active Session</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
            {displayName ? `${greeting}, ${displayName}` : `${greeting}`}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-600 max-w-2xl leading-relaxed">
            Interrogate your health insurance policies with page-grounded citations, simulate medical
            admissions against waiting periods, and verify claim checklists.
          </p>
        </div>

        {/* Primary Command Actions */}
        <div className="flex flex-wrap items-center gap-2.5 self-start md:self-auto">
          {primaryPolicyId ? (
            <Link
              to={`/claim-rehearsal?policy=${encodeURIComponent(primaryPolicyId)}`}
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 transition active:scale-98 focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
            >
              <ClipboardCheck className="h-4 w-4" />
              <span>Start Claim Rehearsal</span>
            </Link>
          ) : (
            <Link
              to="/claim-rehearsal"
              className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-xs font-semibold text-white shadow-xs hover:bg-emerald-700 transition active:scale-98 focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
            >
              <ClipboardCheck className="h-4 w-4" />
              <span>Claim Rehearsal</span>
            </Link>
          )}

          <Link
            to="/library"
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50 transition active:scale-98 focus-visible:ring-2 focus-visible:ring-slate-400 focus:outline-hidden"
          >
            <Upload className="h-3.5 w-3.5 text-slate-500" />
            <span>Upload Schedule</span>
          </Link>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* 2. ACTIVE POLICY FOCUS BAR (WITH POINTER PARALLAX & FLOATING BADGES)  */}
      {/* ===================================================================== */}
      {isLoading ? (
        /* Calm Skeleton State — Prevents layout thrashing and false empty-state alert */
        <div className="dash-active-bar rounded-xl border border-slate-200 bg-slate-100/70 p-4 sm:p-5 animate-pulse">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-start gap-3 w-full max-w-xl">
              <div className="h-10 w-10 rounded-lg bg-slate-300/80 shrink-0" />
              <div className="space-y-2 w-full">
                <div className="h-3.5 bg-slate-300/80 rounded w-1/3" />
                <div className="h-4 bg-slate-300/80 rounded w-3/4" />
                <div className="h-3 bg-slate-200 rounded w-1/2" />
              </div>
            </div>
            <div className="h-8 w-28 bg-slate-300/80 rounded-lg shrink-0 self-start sm:self-auto" />
          </div>
        </div>
      ) : primaryPolicy ? (
        <div
          ref={activeBarRef}
          onMouseMove={handleActiveBarMouseMove}
          onMouseLeave={handleActiveBarMouseLeave}
          className="dash-active-bar relative transform-gpu rounded-xl border border-slate-800 bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 p-4 sm:p-5 text-white shadow-md transition-shadow duration-300"
          style={{ transformStyle: 'preserve-3d' }}
        >
          {/* Floating Badge 1: Top Right (Landing Page Treatment) */}
          <div
            ref={badgeTopRef}
            className="hero-float-badge absolute -top-3.5 right-6 z-20 hidden md:flex items-center gap-1.5 rounded-full bg-slate-900/90 text-white px-3 py-1 text-[10px] font-semibold shadow-md border border-slate-700/80 backdrop-blur-xs animate-float-gentle"
          >
            <Sparkles className="h-3 w-3 text-emerald-400" />
            <span>Verbatim Grounded Clause Engine</span>
          </div>

          {/* Floating Badge 2: Bottom Right (Landing Page Treatment) */}
          <div
            ref={badgeBottomRef}
            className="hero-float-badge absolute -bottom-3 right-8 z-20 hidden lg:flex items-center gap-1.5 rounded-full bg-white text-emerald-800 px-3 py-1 text-[10px] font-bold shadow-md border border-emerald-200 backdrop-blur-xs animate-float-delayed"
          >
            <ShieldCheck className="h-3 w-3 text-emerald-600" />
            <span>Zero Hallucination Retrieval</span>
          </div>

          {/* Floating Badge 3: Top Left (Landing Page Treatment) */}
          <div
            ref={badgeLeftRef}
            className="hero-float-badge absolute -top-3.5 left-10 z-20 hidden xl:flex items-center gap-1.5 rounded-full bg-emerald-950/90 text-emerald-300 px-3 py-1 text-[10px] font-semibold shadow-md border border-emerald-500/30 backdrop-blur-xs animate-pulse-ambient"
          >
            <Shield className="h-3 w-3 text-emerald-400" />
            <span>100% Deterministic Engine</span>
          </div>

          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div className="flex items-start gap-3.5 min-w-0 w-full">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <FileCheck className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400">
                    Primary Active Schedule
                  </span>
                  <span className="rounded bg-white/10 px-1.5 py-0.2 text-[10px] font-medium text-slate-300">
                    {primaryPolicy.page_count ?? 1} Pages
                  </span>
                  <span className="rounded bg-white/10 px-1.5 py-0.2 text-[10px] font-medium text-slate-300">
                    {primaryPolicy.total_chunks ?? primaryPolicy.metadata?.chunk_count ?? 0} Chunks
                  </span>
                  <span
                    className={`rounded px-1.5 py-0.2 text-[10px] font-semibold ${
                      primaryPolicy.status === 'bundled' || primaryPolicy.processing_status === 'bundled'
                        ? 'bg-blue-500/20 text-blue-300 border border-blue-400/30'
                        : 'bg-emerald-500/20 text-emerald-300 border border-emerald-400/30'
                    }`}
                  >
                    {primaryPolicy.status === 'bundled' || primaryPolicy.processing_status === 'bundled'
                      ? 'Bundled Demo'
                      : 'Verified Upload'}
                  </span>
                </div>

                <h2 className="mt-1 text-sm sm:text-base font-bold text-white break-words sm:truncate sm:max-w-xl">
                  {primaryPolicy.filename || primaryPolicy.document_name || 'Policy Schedule'}
                </h2>
                <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">
                  Verified in memory. Clause citations, waiting period simulations, and room-rent calculations are bound to this schedule.
                </p>
              </div>
            </div>

            {/* Quick Action Triggers for Active Policy */}
            <div className="grid grid-cols-2 sm:flex sm:flex-wrap items-center gap-2 w-full lg:w-auto shrink-0 pt-3 lg:pt-0 border-t border-slate-700/60 lg:border-t-0">
              <Link
                to={`/claim-rehearsal?policy=${encodeURIComponent(primaryPolicyId)}`}
                className="col-span-2 sm:col-auto inline-flex items-center justify-center gap-1.5 rounded-lg bg-emerald-500 px-3.5 py-2 sm:py-1.5 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition active:scale-98 shadow-xs focus-visible:ring-2 focus-visible:ring-emerald-400 focus:outline-hidden"
              >
                <ClipboardCheck className="h-3.5 w-3.5" />
                <span>Rehearse Claim</span>
              </Link>
              <Link
                to={`/ask?policy=${encodeURIComponent(primaryPolicyId)}`}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-slate-800 border border-slate-700 px-3 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700 transition focus-visible:ring-2 focus-visible:ring-slate-400 focus:outline-hidden"
              >
                <MessageSquare className="h-3.5 w-3.5 text-emerald-400" />
                <span>Ask Clauses</span>
              </Link>
              <Link
                to={`/explorer?policy=${encodeURIComponent(primaryPolicyId)}`}
                className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-white/5 border border-white/10 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 transition focus-visible:ring-2 focus-visible:ring-slate-400 focus:outline-hidden"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                <span>Explore</span>
              </Link>
              <button
                onClick={() =>
                  handleDownloadPolicy(
                    primaryPolicyId,
                    primaryPolicy.filename || 'Policy_Schedule.pdf'
                  )
                }
                disabled={downloadingId === primaryPolicyId}
                title="Download original verified PDF"
                className="inline-flex items-center justify-center gap-1 rounded-lg bg-white/5 border border-white/10 px-2 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 transition disabled:opacity-50"
              >
                <Download className="h-3.5 w-3.5 text-emerald-400" />
                <span>{downloadingId === primaryPolicyId ? '...' : 'PDF'}</span>
              </button>
            </div>
          </div>
        </div>
      ) : (
        <div className="dash-active-bar rounded-xl border border-dashed border-slate-300 bg-white p-6 text-center">
          <FileText className="mx-auto h-8 w-8 text-slate-300" />
          <h3 className="mt-2 text-sm font-bold text-slate-800">No policy schedules loaded yet</h3>
          <p className="mt-1 text-xs text-slate-500 max-w-md mx-auto">
            Upload your health insurance policy schedule PDF to begin grounded Q&amp;A and claim rehearsals.
          </p>
          <Link
            to="/library"
            className="mt-3.5 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 transition"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Open Document Library</span>
          </Link>
        </div>
      )}

      {/* ===================================================================== */}
      {/* 3. CENTERED ANALYTICAL INTELLIGENCE SUITE                             */}
      {/* ===================================================================== */}
      <div className="dash-suite space-y-6 pt-2">
        {/* Centered Suite Header */}
        <div className="dash-suite-header text-center max-w-3xl mx-auto space-y-2.5">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-50 border border-emerald-200/80 text-[11px] font-bold text-emerald-800 uppercase tracking-wider shadow-2xs">
            <Sparkles className="h-3.5 w-3.5 text-emerald-600" />
            <span>Deterministic Intelligence Suite</span>
            <span className="text-emerald-400">•</span>
            <span className="text-emerald-700">5 Core Simulation &amp; Audit Engines</span>
          </div>
          <h2 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
            Analytical Intelligence Engines
          </h2>
          <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-2xl mx-auto">
            Deterministic simulation, clause extraction, and policy cross-examination engines designed
            for policyholders to stress-test claims, audit exclusions, and eliminate out-of-pocket surprises.
          </p>
        </div>

        {/* Featured Flagship Tool with CardTilt: Pre-Admission Claim Rehearsal */}
        <CardTilt
          as={Link}
          to={
            primaryPolicyId
              ? `/claim-rehearsal?policy=${encodeURIComponent(primaryPolicyId)}`
              : '/claim-rehearsal'
          }
          maxTilt={5}
          spotlightColor="rgba(16, 185, 129, 0.16)"
          className="dash-flagship-card dashboard-card-hover group relative block rounded-2xl border border-emerald-300/90 bg-gradient-to-r from-emerald-50/60 via-white to-emerald-50/30 p-5 sm:p-6 shadow-xs transition hover:border-emerald-600 hover:shadow-md focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
        >
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-5">
            <div className="flex items-start gap-4 min-w-0">
              <div className="flex h-12 w-12 sm:h-14 sm:w-14 shrink-0 items-center justify-center rounded-2xl bg-emerald-600 text-white shadow-sm group-hover:scale-105 transition-transform duration-200">
                <ClipboardCheck className="h-6 w-6 sm:h-7 sm:w-7" />
              </div>
              <div className="min-w-0 flex-1 space-y-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-emerald-700 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white shadow-2xs">
                    Flagship Simulation Engine
                  </span>
                  <span className="text-[11px] font-semibold text-emerald-800">
                    Hospitalization Pre-Auth Stress Test
                  </span>
                </div>
                <h3 className="text-base sm:text-lg font-extrabold text-slate-900 group-hover:text-emerald-800 transition-colors duration-200">
                  Pre-Admission Claim Rehearsal
                </h3>
                <p className="text-xs sm:text-sm text-slate-600 leading-relaxed max-w-3xl">
                  Stress-test a planned hospitalization before admission. Computes room-rent proportionate deductions, validates pre-existing disease waiting periods, and generates an actionable pre-auth documentation checklist.
                </p>

                <div className="flex flex-wrap items-center gap-2 pt-2">
                  <span className="rounded-md bg-white border border-emerald-200/80 px-2.5 py-1 text-[11px] font-semibold text-emerald-900 shadow-2xs">
                    ✓ Pre-Auth Checklist
                  </span>
                  <span className="rounded-md bg-white border border-emerald-200/80 px-2.5 py-1 text-[11px] font-semibold text-emerald-900 shadow-2xs">
                    ✓ Proportionate Rent Deduction
                  </span>
                  <span className="rounded-md bg-white border border-emerald-200/80 px-2.5 py-1 text-[11px] font-semibold text-emerald-900 shadow-2xs">
                    ✓ Co-Payment Risk Engine
                  </span>
                  <span className="rounded-md bg-white border border-emerald-200/80 px-2.5 py-1 text-[11px] font-semibold text-emerald-900 shadow-2xs">
                    ✓ Waiting Period Audit
                  </span>
                </div>
              </div>
            </div>

            <div className="shrink-0 self-start lg:self-center">
              <span className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 sm:py-3 text-xs sm:text-sm font-bold text-white shadow-xs group-hover:bg-emerald-700 group-hover:shadow-sm transition active:scale-98">
                <span>Launch Rehearsal Workspace</span>
                <ArrowRight className="h-4 w-4 group-hover:translate-x-1.5 transition-transform duration-200" />
              </span>
            </div>
          </div>
        </CardTilt>

        {/* Supporting 4 Analytical Tools (4-Column Symmetrical Row on Desktop) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Ask My Policy */}
          <CardTilt
            as={Link}
            to={primaryPolicyId ? `/ask?policy=${encodeURIComponent(primaryPolicyId)}` : '/ask'}
            maxTilt={5}
            spotlightColor="rgba(16, 185, 129, 0.15)"
            className="dash-engine-card dashboard-card-hover group rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs transition hover:border-emerald-500 hover:shadow-sm flex flex-col justify-between focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
          >
            <div>
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700 border border-emerald-200/50 group-hover:scale-110 transition-transform duration-200">
                  <MessageSquare className="h-5 w-5" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700 bg-emerald-50/80 px-2 py-0.5 rounded">
                  Clause Q&amp;A
                </span>
              </div>
              <h4 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-emerald-700 transition-colors duration-200">
                Ask My Policy
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                Ask natural questions regarding cataract limits, organ donor expenses, or day-care procedures with exact page citations.
              </p>
            </div>
            <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-emerald-600 border-t border-slate-100 pt-3">
              <span>Query policy</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1.5 duration-200" />
            </div>
          </CardTilt>

          {/* Scenario Analyzer */}
          <CardTilt
            as={Link}
            to="/scenarios"
            maxTilt={5}
            spotlightColor="rgba(20, 184, 166, 0.15)"
            className="dash-engine-card dashboard-card-hover group rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs transition hover:border-teal-500 hover:shadow-sm flex flex-col justify-between focus-visible:ring-2 focus-visible:ring-teal-500 focus:outline-hidden"
          >
            <div>
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-teal-50 text-teal-700 border border-teal-200/50 group-hover:scale-110 transition-transform duration-200">
                  <Scale className="h-5 w-5" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-teal-700 bg-teal-50/80 px-2 py-0.5 rounded">
                  Simulation
                </span>
              </div>
              <h4 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-teal-700 transition-colors duration-200">
                Scenario Analyzer
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                Deterministically test pre-existing condition timelines, elapsed duration since inception, and age-based copays.
              </p>
            </div>
            <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-teal-600 border-t border-slate-100 pt-3">
              <span>Simulate scenario</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1.5 duration-200" />
            </div>
          </CardTilt>

          {/* Policy Comparison */}
          <CardTilt
            as={Link}
            to="/compare"
            maxTilt={5}
            spotlightColor="rgba(59, 130, 246, 0.15)"
            className="dash-engine-card dashboard-card-hover group rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs transition hover:border-blue-500 hover:shadow-sm flex flex-col justify-between focus-visible:ring-2 focus-visible:ring-blue-500 focus:outline-hidden"
          >
            <div>
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-700 border border-blue-200/50 group-hover:scale-110 transition-transform duration-200">
                  <GitCompare className="h-5 w-5" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-blue-700 bg-blue-50/80 px-2 py-0.5 rounded">
                  Matrix
                </span>
              </div>
              <h4 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-blue-700 transition-colors duration-200">
                Cross-Policy Comparison
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                Side-by-side dimensional matrix comparing 2 health schedules to uncover hidden sublimits and protection gaps.
              </p>
            </div>
            <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-blue-600 border-t border-slate-100 pt-3">
              <span>Compare policies</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1.5 duration-200" />
            </div>
          </CardTilt>

          {/* Policy Explorer */}
          <CardTilt
            as={Link}
            to={
              primaryPolicyId
                ? `/explorer?policy=${encodeURIComponent(primaryPolicyId)}`
                : '/explorer'
            }
            maxTilt={5}
            spotlightColor="rgba(100, 116, 139, 0.15)"
            className="dash-engine-card dashboard-card-hover group rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs transition hover:border-slate-400 hover:shadow-sm flex flex-col justify-between focus-visible:ring-2 focus-visible:ring-slate-400 focus:outline-hidden"
          >
            <div>
              <div className="flex items-center justify-between">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 border border-slate-200/50 group-hover:scale-110 transition-transform duration-200">
                  <FileSpreadsheet className="h-5 w-5" />
                </div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-600 bg-slate-100 px-2 py-0.5 rounded">
                  Audit
                </span>
              </div>
              <h4 className="mt-3.5 text-sm font-bold text-slate-900 group-hover:text-slate-800 transition-colors duration-200">
                Policy Explorer
              </h4>
              <p className="mt-1.5 text-xs text-slate-500 leading-relaxed">
                Inspect verbatim page text extracts, chunk distributions, and extracted candidate clause facts directly.
              </p>
            </div>
            <div className="mt-5 flex items-center gap-1.5 text-xs font-semibold text-slate-600 border-t border-slate-100 pt-3">
              <span>Explore text extracts</span>
              <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-1.5 duration-200" />
            </div>
          </CardTilt>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* 4. POLICY INTELLIGENCE DOCK (EVIDENCE STUDIO & DOCUMENTS SHELF)       */}
      {/* ===================================================================== */}
      <div className="reveal-on-scroll grid grid-cols-1 lg:grid-cols-12 gap-6 items-start pt-2">
        {/* LEFT COLUMN (8 cols): REAL INTERACTIVE POLICY EVIDENCE & CLAUSE STUDIO */}
        <div className="dash-studio lg:col-span-8 rounded-xl border border-slate-200/90 bg-white p-5 sm:p-6 shadow-xs">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
              <div>
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-600" />
                  <h2 className="text-sm sm:text-base font-bold text-slate-900">
                    Policy Evidence &amp; Clause Studio
                  </h2>
                </div>
                <p className="text-xs text-slate-500">
                  {activeEvidence.isRealExtractedFact
                    ? 'Verifiable factual clauses extracted and indexed from your active schedule'
                    : 'Illustrative clause breakdown demonstrating verifiable evidence analysis'}
                </p>
              </div>

              <span
                className={`self-start sm:self-auto rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                  activeEvidence.isRealExtractedFact
                    ? 'bg-emerald-50 text-emerald-800 border-emerald-200/60'
                    : 'bg-slate-100 text-slate-600 border-slate-200'
                }`}
              >
                {activeEvidence.isRealExtractedFact
                  ? 'Real Extracted Facts'
                  : 'Illustrative Benchmark'}
              </span>
            </div>

            {/* Evidence Selector Tabs */}
            <div className="flex overflow-x-auto gap-1 border-b border-slate-100 pb-2 mb-4">
              {evidenceItems.map((item, idx) => (
                <button
                  key={item.id}
                  onClick={() => handleSelectEvidence(idx)}
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition whitespace-nowrap focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden ${
                    activeEvidenceIndex === idx
                      ? 'bg-slate-900 text-white shadow-xs'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
                  }`}
                >
                  {item.tabLabel}
                </button>
              ))}
            </div>

            {/* Dual-Panel Evidence Card (Animated with GSAP on tab switch) */}
            <div
              ref={evidenceCardRef}
              className="grid grid-cols-1 md:grid-cols-2 gap-4 rounded-xl border border-slate-200 bg-slate-50/50 p-4 sm:p-5"
            >
              {/* Left Panel: Verbatim Source Evidence */}
              <div className="flex flex-col justify-between space-y-3 rounded-lg border border-slate-200/80 bg-white p-4 shadow-2xs">
                <div>
                  <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
                    <span className="flex items-center gap-1 text-slate-600 truncate max-w-[200px]">
                      <FileCode className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                      <span className="truncate">{activeEvidence.sourceLabel}</span>
                    </span>
                    <span className="rounded bg-slate-100 px-1.5 py-0.2 text-slate-600 font-mono shrink-0">
                      {activeEvidence.pageCitation}
                    </span>
                  </div>

                  <div className="border-l-2 border-emerald-500 pl-3 py-1 bg-emerald-50/20 rounded-r">
                    <p className="text-xs text-slate-700 italic leading-relaxed">
                      "{activeEvidence.excerpt}"
                    </p>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 flex items-center justify-between pt-2 border-t border-slate-100">
                  <span>Category: {activeEvidence.category}</span>
                  <span className="text-emerald-700 font-semibold">Verified Excerpt</span>
                </div>
              </div>

              {/* Right Panel: Intelligence Verdict & Action */}
              <div className="flex flex-col justify-between space-y-3 rounded-lg border border-slate-200/80 bg-white p-4 shadow-2xs">
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Intelligence Verdict
                    </span>
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                        activeEvidence.verdictType === 'covered'
                          ? 'bg-emerald-100 text-emerald-800'
                          : activeEvidence.verdictType === 'copay'
                          ? 'bg-rose-100 text-rose-800'
                          : activeEvidence.verdictType === 'sublimit'
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-amber-100 text-amber-800'
                      }`}
                    >
                      {activeEvidence.verdictType === 'covered' && (
                        <CheckCircle2 className="h-3 w-3" />
                      )}
                      {activeEvidence.verdictType === 'copay' && <AlertTriangle className="h-3 w-3" />}
                      {activeEvidence.verdictType === 'sublimit' && <Scale className="h-3 w-3" />}
                      {activeEvidence.verdictType === 'waiting' && (
                        <Clock className="h-3 w-3 text-amber-600" />
                      )}
                      <span>{activeEvidence.verdictLabel}</span>
                    </span>
                  </div>

                  <p className="text-xs text-slate-700 leading-relaxed font-normal">
                    {activeEvidence.practicalImpact}
                  </p>
                </div>

                <div className="pt-2 border-t border-slate-100">
                  <Link
                    to={
                      primaryPolicyId
                        ? `${activeEvidence.actionRoute}${
                            activeEvidence.actionRoute.includes('?') ? '&' : '?'
                          }policy=${encodeURIComponent(primaryPolicyId)}`
                        : activeEvidence.actionRoute
                    }
                    className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-700 hover:text-emerald-800 hover:underline focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
                  >
                    <span>{activeEvidence.actionLabel}</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            </div>

            {/* Grounded Direct Inquiry Bar (Immediate First-Viewport Affordance) */}
            <div className="mt-4 pt-4 border-t border-slate-100">
              <form onSubmit={handleDirectQuerySubmit} className="flex gap-2">
                <div className="relative flex-1">
                  <MessageSquare className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    value={directQuery}
                    onChange={(e) => setDirectQuery(e.target.value)}
                    placeholder="Ask a specific clause question (e.g. Is cataract covered?)..."
                    aria-label="Direct policy question"
                    className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-2 pl-9 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500/20 transition"
                  />
                </div>
                <button
                  type="submit"
                  className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-700 transition active:scale-98 shrink-0 focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
                >
                  Ask Policy
                </button>
              </form>

              {/* Quick Prompt Chips */}
              <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                <span className="font-semibold text-slate-600">Suggested Inquiries:</span>
                <button
                  type="button"
                  onClick={() =>
                    navigate(
                      primaryPolicyId
                        ? `/ask?policy=${encodeURIComponent(
                            primaryPolicyId
                          )}&q=What%20is%20the%20waiting%20period%20for%20pre-existing%20diseases%3F`
                        : `/ask?q=What%20is%20the%20waiting%20period%20for%20pre-existing%20diseases%3F`
                    )
                  }
                  className="rounded bg-slate-100 hover:bg-emerald-50 hover:text-emerald-800 px-2 py-0.5 transition"
                >
                  PED Waiting Period
                </button>
                <button
                  type="button"
                  onClick={() =>
                    navigate(
                      primaryPolicyId
                        ? `/ask?policy=${encodeURIComponent(
                            primaryPolicyId
                          )}&q=What%20are%20the%20room%20rent%20sub-limits%20and%20ICU%20caps%3F`
                        : `/ask?q=What%20are%20the%20room%20rent%20sub-limits%20and%20ICU%20caps%3F`
                    )
                  }
                  className="rounded bg-slate-100 hover:bg-emerald-50 hover:text-emerald-800 px-2 py-0.5 transition"
                >
                  Room Rent Sub-limits
                </button>
                <button
                  type="button"
                  onClick={() =>
                    navigate(
                      primaryPolicyId
                        ? `/ask?policy=${encodeURIComponent(
                            primaryPolicyId
                          )}&q=Are%20robotic%20surgeries%20covered%20under%20day-care%3F`
                        : `/ask?q=Are%20robotic%20surgeries%20covered%20under%20day-care%3F`
                    )
                  }
                  className="rounded bg-slate-100 hover:bg-emerald-50 hover:text-emerald-800 px-2 py-0.5 transition"
                >
                  Robotic Surgeries
                </button>
              </div>
            </div>
          </div>

        {/* =================================================================== */}
        {/* RIGHT COLUMN (4 cols): TELEMETRY DOSSIER & DOCUMENT SHELF           */}
        {/* =================================================================== */}
        <div className="dash-shelf lg:col-span-4 space-y-6">
          {/* A. WORKSPACE INTELLIGENCE TELEMETRY */}
          <div className="rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between mb-3.5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                Workspace Telemetry
              </h3>
              <span
                className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                  data?.database_status === 'connected'
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-slate-100 text-slate-600'
                }`}
              >
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    data?.database_status === 'connected' ? 'bg-emerald-500' : 'bg-amber-400'
                  }`}
                />
                <span>
                  {data?.database_status === 'connected' ? 'Atlas Sync' : 'Session Cache'}
                </span>
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-xs text-slate-600">Active Schedules</span>
                <span className="text-sm font-bold text-slate-900">
                  {isLoading ? '—' : <AnimatedCounter value={data?.total_policies ?? 0} />}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-xs text-slate-600">Grounded Consultations</span>
                <span className="text-sm font-bold text-slate-900">
                  {isLoading ? '—' : <AnimatedCounter value={data?.total_conversations ?? 0} />}
                </span>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-100">
                <span className="text-xs text-slate-600">Simulations Executed</span>
                <span className="text-sm font-bold text-slate-900">
                  {isLoading ? '—' : <AnimatedCounter value={data?.total_analyses ?? 0} />}
                </span>
              </div>

              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-slate-600">Active Storage</span>
                <span className="text-xs font-semibold text-slate-800">
                  {data?.database_status === 'connected'
                    ? 'MongoDB Multi-Tenant'
                    : 'Local In-Memory Cache'}
                </span>
              </div>
            </div>
          </div>

          {/* B. LOADED POLICY DOCUMENTS SHELF */}
          <div className="rounded-xl border border-slate-200/90 bg-white p-5 shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-600">
                  Policy Documents Shelf
                </h3>
                <span className="text-[11px] text-slate-500">
                  {data?.recent_policies?.length ?? 0} active in memory
                </span>
              </div>
              <Link
                to="/library"
                className="text-xs font-semibold text-emerald-600 hover:text-emerald-700 focus-visible:ring-2 focus-visible:ring-emerald-500 focus:outline-hidden"
              >
                Manage All
              </Link>
            </div>

            {/* Shelf search */}
            <div className="relative mb-3">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Filter documents..."
                aria-label="Filter documents shelf"
                className="w-full rounded-lg border border-slate-200 bg-slate-50/50 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 focus:border-emerald-500 focus:bg-white focus:outline-hidden focus:ring-1 focus:ring-emerald-500/20 transition"
              />
              {searchTerm && (
                <button
                  onClick={() => setSearchTerm('')}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 text-xs px-1"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Document list */}
            {isLoading ? (
              <div className="space-y-2 py-2">
                <div className="h-14 bg-slate-100 rounded-lg animate-pulse" />
                <div className="h-14 bg-slate-100 rounded-lg animate-pulse" />
              </div>
            ) : filteredPolicies.length > 0 ? (
              <div className="space-y-2.5 max-h-[340px] overflow-y-auto pr-1">
                {filteredPolicies.map((p) => {
                  const name = p.filename || p.document_name || 'Policy Document';
                  const id = p.policy_id || p.id || '';
                  const chunks = p.total_chunks ?? p.metadata?.chunk_count ?? 0;
                  const isBundled = p.status === 'bundled' || p.processing_status === 'bundled';

                  return (
                    <div
                      key={id || name}
                      className="rounded-lg border border-slate-200/80 bg-slate-50/40 p-3 hover:bg-slate-50 transition"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-slate-900 truncate" title={name}>
                            {name}
                          </p>
                          <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-500">
                            <span>{p.page_count ?? 1} pages</span>
                            <span>•</span>
                            <span>{chunks} chunks</span>
                            <span>•</span>
                            <span
                              className={
                                isBundled
                                  ? 'text-blue-700 font-semibold'
                                  : 'text-emerald-700 font-semibold'
                              }
                            >
                              {isBundled ? 'Demo' : 'Uploaded'}
                            </span>
                          </div>
                        </div>

                        {/* Download button */}
                        <button
                          onClick={() => handleDownloadPolicy(id, name)}
                          disabled={downloadingId === id}
                          title="Download original verified PDF"
                          className="shrink-0 p-1 text-slate-400 hover:text-slate-700 transition"
                        >
                          <Download className="h-3.5 w-3.5" />
                        </button>
                      </div>

                      {/* Quick Actions Row */}
                      <div className="mt-2.5 flex items-center justify-between border-t border-slate-200/60 pt-2 text-[11px]">
                        <div className="flex items-center gap-2">
                          <Link
                            to={`/claim-rehearsal?policy=${encodeURIComponent(id)}`}
                            className="font-bold text-emerald-700 hover:text-emerald-800"
                          >
                            Rehearse
                          </Link>
                          <span className="text-slate-300">•</span>
                          <Link
                            to={`/ask?policy=${encodeURIComponent(id)}`}
                            className="font-semibold text-slate-700 hover:text-slate-900"
                          >
                            Ask
                          </Link>
                          <span className="text-slate-300">•</span>
                          <Link
                            to={`/explorer?policy=${encodeURIComponent(id)}`}
                            className="font-medium text-slate-500 hover:text-slate-800"
                          >
                            Explore
                          </Link>
                        </div>

                        {!isBundled && (
                          <button
                            onClick={() => handleDeletePolicy(id, name)}
                            disabled={deletingId === id}
                            className="text-rose-600 hover:text-rose-700 text-[10px] font-semibold"
                          >
                            {deletingId === id ? '...' : 'Delete'}
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="py-6 text-center text-xs text-slate-400">
                {searchTerm ? 'No policies match search' : 'No policies loaded in session'}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
