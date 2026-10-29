import React, { useState, useEffect, useRef, useLayoutEffect } from 'react';
import { Link } from 'react-router-dom';
import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import {
  Shield,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  FileText,
  Search,
  Scale,
  ClipboardCheck,
  GitCompare,
  ArrowRight,
  Menu,
  X,
  FileCheck,
  ChevronRight,
  ChevronDown,
  Info,
  Calendar,
  IndianRupee,
  Activity,
  Layers,
  RotateCcw,
  Check,
  HelpCircle,
  Zap,
  SlidersHorizontal,
  Lock,
  Sparkles,
  Eye,
  ArrowUpRight,
  FileCode,
  CheckCheck,
  Compass,
  AlertCircle,
  Calculator,
  BookOpen,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Footer } from '../components/Footer';

// Register GSAP ScrollTrigger plugin once
gsap.registerPlugin(ScrollTrigger);

// ============================================================================
// Types & Data Models
// ============================================================================

interface SampleScenario {
  id: string;
  category: string;
  title: string;
  verdict: 'covered' | 'active_waiting' | 'sublimit' | 'excluded';
  verdictLabel: string;
  policyExcerpt: string;
  pageCitation: string;
  chunkId: string;
  plainExplanation: string;
  rehearsalNote: string;
}

const SAMPLE_SCENARIOS: SampleScenario[] = [
  {
    id: 'room-rent',
    category: 'Room Rent Capping',
    title: 'Single Private A/C Room & Boarding',
    verdict: 'covered',
    verdictLabel: 'Covered Without Daily Cap',
    policyExcerpt:
      'Room, boarding and nursing expenses incurred during hospital stay are payable up to Single Private A/C Room category without daily monetary limit. No proportionate deduction shall be levied on associated medical bills.',
    pageCitation: 'Page 12, Section 3.1(a)',
    chunkId: '#RR-CAP-01',
    plainExplanation:
      'You can select any standard Single Private A/C Room. The hospital bill will not trigger proportional reductions on doctor consultations, nursing, or surgeon fees.',
    rehearsalNote: 'Zero proportionate deduction risk detected for planned admission.',
  },
  {
    id: 'ped-waiting',
    category: 'Pre-Existing Disease',
    title: 'Type-2 Diabetes & Hypertension (PED)',
    verdict: 'active_waiting',
    verdictLabel: 'Waiting Period Active (18 mos remaining)',
    policyExcerpt:
      'Pre-existing diseases (PED) as declared at proposal inception shall be covered after thirty-six (36) months of continuous coverage from the original policy inception date.',
    pageCitation: 'Page 16, Section 4.1',
    chunkId: '#PED-WAIT-03',
    plainExplanation:
      'Based on an active policy duration of 18 months, treatments directly attributable to your pre-existing diabetes condition are in the active waiting period for 18 more months.',
    rehearsalNote: 'Claims for declared PED are non-payable until month 36.',
  },
  {
    id: 'robotic-surgery',
    category: 'Modern Treatments',
    title: 'Robotic-Assisted Knee Surgery',
    verdict: 'sublimit',
    verdictLabel: 'Sub-Limit Applied (50% Sum Insured)',
    policyExcerpt:
      'Modern treatments including Robotic Surgery and Stereotactic Radio-therapy are covered subject to a sub-limit of 50% of the base Sum Insured or Rs. 2,50,000, whichever is lower.',
    pageCitation: 'Page 22, Section 5.4(c)',
    chunkId: '#MOD-SURG-09',
    plainExplanation:
      'Robotic surgery is eligible, but capped at ₹2,50,000 under your ₹5 Lakh Sum Insured schedule. Any expense beyond this sub-limit requires self-funding or a top-up policy.',
    rehearsalNote: 'Check surgeon estimates against the ₹2.5 Lakh modern treatment ceiling.',
  },
  {
    id: 'cosmetic-exclusion',
    category: 'Permanent Exclusion',
    title: 'Aesthetic & Cosmetic Procedures',
    verdict: 'excluded',
    verdictLabel: 'Permanently Excluded',
    policyExcerpt:
      'Expenses related to any admission primarily for cosmetic or plastic surgery, aesthetic treatments, or weight loss treatments are permanently excluded under Code Excl-02.',
    pageCitation: 'Page 28, Section 6.2',
    chunkId: '#EXCL-PERM-02',
    plainExplanation:
      'Aesthetic and weight management surgeries are permanently excluded under standard IRDAI guidelines unless necessitated by reconstructive surgery following accidental trauma.',
    rehearsalNote: 'Procedure matches mandatory permanent exclusion clause.',
  },
];

interface ComparisonFeature {
  id: string;
  name: string;
  category: string;
  planA: string;
  planB: string;
  differs: boolean;
  impactExplanation: string;
}

const COMPARISON_FEATURES: ComparisonFeature[] = [
  {
    id: 'room-rent',
    name: 'Room Rent Limit',
    category: 'In-Patient',
    planA: '1% of Sum Insured / day (₹5,000 cap)',
    planB: 'Single Private A/C Room (No daily limit)',
    differs: true,
    impactExplanation:
      'Plan A triggers proportionate deductions across doctor fees and surgery if room rent exceeds 1%. Plan B eliminates this risk.',
  },
  {
    id: 'ped-wait',
    name: 'Pre-Existing Disease Wait',
    category: 'Waiting Periods',
    planA: '36 Months continuous coverage',
    planB: '24 Months continuous coverage',
    differs: true,
    impactExplanation:
      'Plan B covers declared diabetes, hypertension, and cardiac history 12 months earlier.',
  },
  {
    id: 'robotic-surgery',
    name: 'Modern & Robotic Surgeries',
    category: 'Sub-Limits',
    planA: 'Capped at ₹2,00,000 per admission',
    planB: '100% of Sum Insured (Up to ₹10 Lakh)',
    differs: true,
    impactExplanation:
      'Robotic-assisted procedures for oncology or joint replacement incur out-of-pocket costs on Plan A.',
  },
  {
    id: 'copay',
    name: 'Senior Citizen Co-payment',
    category: 'Cost Sharing',
    planA: '20% co-payment for ages 61 and above',
    planB: '0% co-payment across all age bands',
    differs: true,
    impactExplanation:
      'On a ₹4 Lakh hospital bill, Plan A requires ₹80,000 paid by the policyholder regardless of sum insured.',
  },
  {
    id: 'pre-post',
    name: 'Pre & Post Hospitalization',
    category: 'Recovery',
    planA: '30 Days Pre / 60 Days Post',
    planB: '60 Days Pre / 180 Days Post',
    differs: true,
    impactExplanation:
      'Plan B pays for follow-up investigations, diagnostic scans, and medicines for 6 full months post-discharge.',
  },
];

interface FAQItem {
  id: string;
  question: string;
  answer: string;
}

const FAQS: FAQItem[] = [
  {
    id: 'faq-1',
    question: 'What makes CoverScope different from generic AI chatbots?',
    answer:
      'Generic AI chatbots frequently hallucinate clauses, invent sub-limits, or assume American insurance terminology. CoverScope is built specifically for Indian health insurance and IRDAI regulations. Every answer is run through an anti-hallucination verification gate: clauses must be verbatim substrings extracted from your actual uploaded PDF, complete with page coordinates and chunk IDs.',
  },
  {
    id: 'faq-2',
    question: 'How does verbatim clause extraction and grounding work?',
    answer:
      'When you upload an official policy schedule or wordings document, our backend processes each page via PyMuPDF and creates indexed chunks. When you query the platform or simulate a medical scenario, CoverScope retrieves candidate chunks, extracts the exact contractual language, and verifies that the cited text matches the original document before providing plain-English guidance.',
  },
  {
    id: 'faq-3',
    question: 'Does a positive scenario analysis guarantee claim approval?',
    answer:
      'No. CoverScope is an educational intelligence and pre-admission analysis tool. It empowers you to understand what your contract covers, spot hidden sub-limits, and avoid proportionate deductions before hospital admission. Formal claim authorization, cashless issuance, and final settlements are strictly adjudicated by your insurer and licensed Third Party Administrator (TPA) based on original hospital bills and medical documentation.',
  },
  {
    id: 'faq-4',
    question: 'How are my uploaded policy documents stored and protected?',
    answer:
      'Your uploaded PDF documents are stored in MongoDB Atlas GridFS with strict per-tenant isolation linked directly to your authenticated account ID. Cross-user document queries or unauthorized history deletions are prevented by backend ownership verification. Your private policy documents are never pooled or used to train public foundation models.',
  },
];

// ============================================================================
// CardTilt Component with Pointer-Driven Spotlight
// ============================================================================

interface CardTiltProps {
  children: React.ReactNode;
  className?: string;
  maxTilt?: number;
  spotlight?: boolean;
}

const CardTilt: React.FC<CardTiltProps> = ({
  children,
  className = '',
  maxTilt = 6,
  spotlight = true,
}) => {
  const cardRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isHovered, setIsHovered] = useState(false);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setCoords({ x, y });

    const normX = x / rect.width - 0.5;
    const normY = y / rect.height - 0.5;

    if (
      window.matchMedia('(pointer: fine)').matches &&
      !window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      gsap.to(cardRef.current, {
        rotateY: normX * maxTilt,
        rotateX: -normY * maxTilt,
        transformPerspective: 1000,
        ease: 'power2.out',
        duration: 0.25,
      });
    }
  };

  const handleMouseEnter = () => setIsHovered(true);

  const handleMouseLeave = () => {
    setIsHovered(false);
    if (!cardRef.current) return;
    gsap.to(cardRef.current, {
      rotateX: 0,
      rotateY: 0,
      ease: 'power2.out',
      duration: 0.45,
    });
  };

  return (
    <div
      ref={cardRef}
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      className={`relative transform-gpu transition-shadow duration-300 ${className}`}
      style={{
        transformStyle: 'preserve-3d',
      }}
    >
      {spotlight && isHovered && (
        <div
          className="pointer-events-none absolute -inset-px rounded-[inherit] transition-opacity duration-300 z-10"
          style={{
            background: `radial-gradient(360px circle at ${coords.x}px ${coords.y}px, rgba(16, 185, 129, 0.08), transparent 80%)`,
          }}
          aria-hidden="true"
        />
      )}
      {children}
    </div>
  );
};

// ============================================================================
// Main Signature Landing Page
// ============================================================================

export const LandingPage: React.FC = () => {
  const { isAuthenticated } = useAuth();
  const rootRef = useRef<HTMLDivElement>(null);

  // Scroll & Navigation states
  const [isScrolled, setIsScrolled] = useState(false);
  const [scrollProgress, setScrollProgress] = useState(0);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Interactive component states
  const [activeScenarioId, setActiveScenarioId] = useState<string>('room-rent');
  const [activeCapabilityTab, setActiveCapabilityTab] = useState<
    'explorer' | 'ask' | 'scenarios' | 'rehearsal'
  >('ask');
  const [clauseWalkthroughStep, setClauseWalkthroughStep] = useState<number>(1);
  const [isWalkthroughPlaying, setIsWalkthroughPlaying] = useState<boolean>(false);
  const [comparisonFilter, setComparisonFilter] = useState<'all' | 'diffs'>('all');
  const [openFaqId, setOpenFaqId] = useState<string | null>('faq-1');

  // Parallax refs for hero signature visual
  const heroCardRef = useRef<HTMLDivElement>(null);
  const badgeTopRef = useRef<HTMLDivElement>(null);
  const badgeBottomRef = useRef<HTMLDivElement>(null);
  const badgeRightRef = useRef<HTMLDivElement>(null);

  // Financial simulation state in Chapter D
  const [simulatedBillAmount, setSimulatedBillAmount] = useState<number>(400000);

  // Scroll progress & sticky navbar listener
  useEffect(() => {
    let ticking = false;
    const handleScroll = () => {
      const scrollTop = window.scrollY;
      setIsScrolled(scrollTop > 24);

      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const progress =
        docHeight > 0 ? Math.min(100, Math.max(0, (scrollTop / docHeight) * 100)) : 0;
      setScrollProgress(progress);
      ticking = false;
    };

    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(handleScroll);
        ticking = true;
      }
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Clause-to-explanation auto-walkthrough timer
  useEffect(() => {
    if (!isWalkthroughPlaying) return;
    const interval = setInterval(() => {
      setClauseWalkthroughStep((prev) => {
        if (prev >= 3) {
          setIsWalkthroughPlaying(false);
          return 3;
        }
        return prev + 1;
      });
    }, 2800);
    return () => clearInterval(interval);
  }, [isWalkthroughPlaying]);

  // ============================================================================
  // GSAP Choreographed Master Motion System (Synchronous Layout Phase to prevent FOUC)
  // ============================================================================
  useLayoutEffect(() => {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const ctx = gsap.context(() => {
      if (prefersReducedMotion) {
        gsap.set(
          [
            '.hero-nav-bar',
            '.hero-eyebrow',
            '.hero-text-line',
            '.hero-subtext',
            '.hero-cta',
            '.hero-trust',
            '.hero-signature-workspace',
            '.hero-float-badge',
            '.reveal-section',
            '.stagger-card',
          ],
          { opacity: 1, y: 0, scale: 1, clearProps: 'all' }
        );
        return;
      }

      // 1. Hero Entrance Master Timeline - begins immediately without artificial delay
      const heroTl = gsap.timeline({
        defaults: { ease: 'power4.out' },
      });

      // Navigation arrives subtly from above
      heroTl.fromTo(
        '.hero-nav-bar',
        { y: -24, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.7, ease: 'power2.out' }
      );

      // Small eyebrow appears
      heroTl.fromTo(
        '.hero-eyebrow',
        { y: 16, opacity: 0, scale: 0.95 },
        { y: 0, opacity: 1, scale: 1, duration: 0.6 },
        '-=0.4'
      );

      // Headline lines reveal through masks with deliberate staggering
      heroTl.fromTo(
        '.hero-text-line',
        { yPercent: 115, opacity: 0 },
        { yPercent: 0, opacity: 1, duration: 0.85, stagger: 0.12, ease: 'power4.out' },
        '-=0.35'
      );

      // Supporting copy enters after headline begins to settle
      heroTl.fromTo(
        '.hero-subtext',
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.65 },
        '-=0.45'
      );

      // CTAs enter with restrained easing response
      heroTl.fromTo(
        '.hero-cta',
        { y: 20, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.6, stagger: 0.1, ease: 'power3.out' },
        '-=0.4'
      );

      // Trust metrics
      heroTl.fromTo(
        '.hero-trust',
        { y: 15, opacity: 0 },
        { y: 0, opacity: 1, duration: 0.5, stagger: 0.08 },
        '-=0.3'
      );

      // The signature policy document workspace rises into view
      heroTl.fromTo(
        '.hero-signature-workspace',
        { y: 55, scale: 0.94, opacity: 0 },
        { y: 0, scale: 1, opacity: 1, duration: 0.95, ease: 'power3.out' },
        '-=0.75'
      );

      // Floating chips enter in secondary sequence with subtle spring
      heroTl.fromTo(
        '.hero-float-badge',
        { scale: 0.8, opacity: 0, y: 14 },
        { scale: 1, opacity: 1, y: 0, duration: 0.6, stagger: 0.12, ease: 'back.out(1.5)' },
        '-=0.45'
      );

      // 2. ScrollTrigger Section Reveals
      gsap.utils.toArray<HTMLElement>('.reveal-section').forEach((section) => {
        gsap.fromTo(
          section,
          { y: 35, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.8,
            ease: 'power3.out',
            scrollTrigger: {
              trigger: section,
              start: 'top 85%',
              toggleActions: 'play none none none',
            },
          }
        );
      });

      // 3. Staggered Grid Cards on Scroll
      gsap.utils.toArray<HTMLElement>('.stagger-grid').forEach((grid) => {
        const cards = grid.querySelectorAll('.stagger-card');
        if (!cards.length) return;
        gsap.fromTo(
          cards,
          { y: 30, opacity: 0 },
          {
            y: 0,
            opacity: 1,
            duration: 0.7,
            stagger: 0.12,
            ease: 'power2.out',
            scrollTrigger: {
              trigger: grid,
              start: 'top 82%',
              toggleActions: 'play none none none',
            },
          }
        );
      });
    }, rootRef);

    return () => ctx.revert();
  }, []);

  // Pointer-driven parallax for the signature workspace (desktop mouse only)
  const handleHeroMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (
      !heroCardRef.current ||
      !window.matchMedia('(pointer: fine)').matches ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    )
      return;

    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;

    gsap.to(heroCardRef.current, {
      rotateY: x * 5,
      rotateX: -y * 5,
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
    if (badgeRightRef.current) {
      gsap.to(badgeRightRef.current, {
        x: x * 10,
        y: -y * 10,
        ease: 'power1.out',
        duration: 0.35,
      });
    }
  };

  const handleHeroMouseLeave = () => {
    if (!heroCardRef.current) return;
    gsap.to(heroCardRef.current, {
      rotateX: 0,
      rotateY: 0,
      ease: 'power2.out',
      duration: 0.55,
    });
    if (badgeTopRef.current) gsap.to(badgeTopRef.current, { x: 0, y: 0, duration: 0.55 });
    if (badgeBottomRef.current) gsap.to(badgeBottomRef.current, { x: 0, y: 0, duration: 0.55 });
    if (badgeRightRef.current) gsap.to(badgeRightRef.current, { x: 0, y: 0, duration: 0.55 });
  };

  const selectedScenario =
    SAMPLE_SCENARIOS.find((s) => s.id === activeScenarioId) || SAMPLE_SCENARIOS[0];

  const getVerdictBadge = (verdict: SampleScenario['verdict'], label: string) => {
    switch (verdict) {
      case 'covered':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            {label}
          </span>
        );
      case 'active_waiting':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-800 border border-amber-200">
            <Calendar className="h-3.5 w-3.5 text-amber-600" />
            {label}
          </span>
        );
      case 'sublimit':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-800 border border-blue-200">
            <IndianRupee className="h-3.5 w-3.5 text-blue-600" />
            {label}
          </span>
        );
      case 'excluded':
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-800 border border-rose-200">
            <XCircle className="h-3.5 w-3.5 text-rose-600" />
            {label}
          </span>
        );
    }
  };

  const handleStartWalkthrough = () => {
    setClauseWalkthroughStep(1);
    setIsWalkthroughPlaying(true);
  };

  const handleCapabilityTabKeyDown = (
    e: React.KeyboardEvent,
    currentIndex: number
  ) => {
    const tabs: Array<'explorer' | 'ask' | 'scenarios' | 'rehearsal'> = [
      'explorer',
      'ask',
      'scenarios',
      'rehearsal',
    ];
    if (e.key === 'ArrowRight') {
      e.preventDefault();
      const nextIdx = (currentIndex + 1) % tabs.length;
      setActiveCapabilityTab(tabs[nextIdx]);
      document.getElementById(`tab-${tabs[nextIdx]}`)?.focus();
    } else if (e.key === 'ArrowLeft') {
      e.preventDefault();
      const prevIdx = (currentIndex - 1 + tabs.length) % tabs.length;
      setActiveCapabilityTab(tabs[prevIdx]);
      document.getElementById(`tab-${tabs[prevIdx]}`)?.focus();
    }
  };

  const filteredComparison =
    comparisonFilter === 'diffs'
      ? COMPARISON_FEATURES.filter((f) => f.differs)
      : COMPARISON_FEATURES;

  // Financial simulation calculations for Chapter D
  // Assuming ₹5,00,000 Sum Insured with 1% Room Rent Limit (₹5,000/day cap)
  // Actual room rate chosen: ₹8,000/day. Proportionate ratio = 5000 / 8000 = 62.5% paid by insurer.
  // Associated charges roughly 70% of bill. Insurer pays 62.5% of associated charges -> 37.5% out-of-pocket penalty.
  const associatedExpenses = simulatedBillAmount * 0.7;
  const planAPenalty = Math.round(associatedExpenses * (1 - 5000 / 8000));
  const planAOutOfPocket = Math.min(simulatedBillAmount, planAPenalty + 12000); // 12k room delta + associated penalty
  const planBOutOfPocket = 0; // Uncapped Single AC Room covers 100%

  return (
    <div
      ref={rootRef}
      className="min-h-screen bg-[#fafbfb] text-slate-900 font-sans overflow-x-hidden"
    >
      {/* ===================================================================== */}
      {/* SCROLL PROGRESS INDICATOR */}
      {/* ===================================================================== */}
      <div
        className="fixed top-0 left-0 right-0 h-[3px] bg-transparent z-50 pointer-events-none"
        aria-hidden="true"
      >
        <div
          className="h-full bg-gradient-to-r from-emerald-500 via-teal-500 to-emerald-600 transition-[width] duration-150 ease-out"
          style={{ width: `${scrollProgress}%` }}
        />
      </div>

      {/* ===================================================================== */}
      {/* 1. PUBLIC SMART STICKY NAVIGATION */}
      {/* ===================================================================== */}
      <header
        className={`hero-nav-bar sticky top-0 z-40 w-full transition-all duration-300 ${
          isScrolled
            ? 'border-b border-slate-200/90 bg-white/95 backdrop-blur-md shadow-xs'
            : 'border-b border-transparent bg-white/80 backdrop-blur-sm'
        }`}
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
          {/* Logo Identity */}
          <Link
            to="/"
            className="flex items-center gap-2.5 transition-transform duration-200 hover:scale-[1.01] active:scale-[0.99] focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 rounded-lg"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white shadow-xs shadow-emerald-600/20">
              <Shield className="h-5 w-5 stroke-[2.4]" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900">
                Cover<span className="text-emerald-600">Scope</span>
              </span>
              <span className="hidden sm:inline-block ml-2 text-[10px] font-semibold text-slate-400 uppercase tracking-widest">
                Policy Intelligence
              </span>
            </div>
          </Link>

          {/* Desktop Nav Links */}
          <nav
            className="hidden md:flex items-center gap-7 text-xs font-medium text-slate-600"
            aria-label="Main Navigation"
          >
            <a
              href="#problem"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              The Problem
            </a>
            <a
              href="#transformation"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              Clause Grounding
            </a>
            <a
              href="#capabilities"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              Capabilities
            </a>
            <a
              href="#financial-impact"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              Financial Impact
            </a>
            <a
              href="#workflow"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              Workflow
            </a>
            <a
              href="#faq"
              className="hover:text-emerald-700 transition-colors py-1 focus:outline-hidden focus-visible:text-emerald-700"
            >
              FAQ
            </a>
          </nav>

          {/* Header Action Buttons */}
          <div className="hidden sm:flex items-center gap-3 text-xs">
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 font-semibold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="rounded-xl px-3.5 py-2 font-medium text-slate-700 hover:text-slate-900 hover:bg-slate-100/80 active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-400"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 font-semibold text-white shadow-xs hover:bg-emerald-700 active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
                >
                  <span>Get started</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
            className="md:hidden rounded-lg p-2 text-slate-600 hover:bg-slate-100 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        {mobileMenuOpen && (
          <div className="border-b border-slate-200 bg-white px-4 py-4 md:hidden text-sm space-y-3 shadow-md animate-in slide-in-from-top-2 duration-150">
            <nav className="flex flex-col space-y-2 font-medium text-slate-700">
              <a
                href="#problem"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                The Problem
              </a>
              <a
                href="#transformation"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                Clause Grounding
              </a>
              <a
                href="#capabilities"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                Capabilities
              </a>
              <a
                href="#financial-impact"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                Financial Impact
              </a>
              <a
                href="#workflow"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                Workflow
              </a>
              <a
                href="#faq"
                onClick={() => setMobileMenuOpen(false)}
                className="px-2 py-1.5 rounded-lg hover:bg-slate-50 hover:text-emerald-700 transition"
              >
                FAQ
              </a>
            </nav>

            <div className="border-t border-slate-100 pt-3 flex flex-col gap-2">
              {isAuthenticated ? (
                <Link
                  to="/dashboard"
                  onClick={() => setMobileMenuOpen(false)}
                  className="w-full text-center rounded-xl bg-emerald-600 py-2.5 text-xs font-semibold text-white shadow-xs"
                >
                  Go to Dashboard
                </Link>
              ) : (
                <>
                  <Link
                    to="/login"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center rounded-xl border border-slate-200 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                  >
                    Sign in
                  </Link>
                  <Link
                    to="/register"
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full text-center rounded-xl bg-emerald-600 py-2.5 text-xs font-semibold text-white shadow-xs"
                  >
                    Get started
                  </Link>
                </>
              )}
            </div>
          </div>
        )}
      </header>

      {/* ===================================================================== */}
      {/* 2. THE SIGNATURE HERO VIEWPORT (Section 3 Standard) */}
      {/* ===================================================================== */}
      <section
        onMouseMove={handleHeroMouseMove}
        onMouseLeave={handleHeroMouseLeave}
        className="relative overflow-hidden pt-12 pb-24 lg:pt-16 lg:pb-32 bg-[radial-gradient(#0f172a08_1px,transparent_1px)] [background-size:28px_28px]"
      >
        {/* Soft Ambient Radial Glow Backdrops */}
        <div
          className="pointer-events-none absolute top-10 left-1/2 -translate-x-1/2 h-[680px] w-full max-w-7xl -z-10 overflow-hidden"
          aria-hidden="true"
        >
          <div className="absolute top-0 left-1/4 h-80 w-80 rounded-full bg-emerald-200/35 blur-3xl animate-pulse-ambient" />
          <div className="absolute top-20 right-1/4 h-96 w-96 rounded-full bg-teal-200/25 blur-3xl animate-glow-shift" />
        </div>

        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {/* Top Hero Messaging Centerpiece */}
          <div className="text-center max-w-3xl mx-auto space-y-6 mb-12 lg:mb-16">
            {/* Eyebrow */}
            <div className="hero-eyebrow inline-flex items-center gap-2 rounded-full border border-emerald-600/25 bg-emerald-50/90 px-4 py-1.5 text-xs font-bold uppercase tracking-wider text-emerald-800 shadow-2xs backdrop-blur-xs">
              <Shield className="h-3.5 w-3.5 text-emerald-600" />
              <span>INSURANCE, MADE UNDERSTANDABLE</span>
            </div>

            {/* Headline with Masked Reveals */}
            <h1 className="text-4xl font-extrabold tracking-tight text-slate-950 sm:text-5xl lg:text-[60px] leading-[1.08]">
              <span className="block overflow-hidden py-1">
                <span className="hero-text-line block">Your policy.</span>
              </span>
              <span className="block overflow-hidden py-1">
                <span className="hero-text-line block text-emerald-700">Made clear.</span>
              </span>
            </h1>

            {/* Supporting Copy */}
            <p className="hero-subtext text-base sm:text-lg text-slate-600 leading-relaxed max-w-2xl mx-auto">
              Understand what your insurance covers, what it excludes, and what the fine print could
              mean for you — with explanations grounded in your policy.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-center justify-center gap-3.5 pt-2">
              <div className="hero-cta w-full sm:w-auto">
                <Link
                  to={isAuthenticated ? '/dashboard' : '/register'}
                  className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-7 py-3.5 text-sm font-semibold text-white shadow-xs hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
                >
                  <span>{isAuthenticated ? 'Explore your policy' : 'Explore your policy'}</span>
                  <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
                </Link>
              </div>

              <div className="hero-cta w-full sm:w-auto">
                <a
                  href="#transformation"
                  className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-slate-300 bg-white px-6 py-3.5 text-sm font-semibold text-slate-700 shadow-2xs hover:bg-slate-50 hover:border-slate-400 active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-400"
                >
                  <span>See how it works</span>
                  <ChevronRight className="h-4 w-4 text-slate-400 transition-transform duration-200 group-hover:translate-x-0.5" />
                </a>
              </div>
            </div>

            {/* Trust Badges */}
            <div className="pt-6 border-t border-slate-200/70 grid grid-cols-3 gap-3 text-center max-w-xl mx-auto">
              <div className="hero-trust">
                <div className="text-xs font-bold text-slate-900">100% Verbatim</div>
                <div className="text-[11px] text-slate-500">Document citations</div>
              </div>
              <div className="hero-trust">
                <div className="text-xs font-bold text-slate-900">Anti-Hallucination</div>
                <div className="text-[11px] text-slate-500">Substring gate</div>
              </div>
              <div className="hero-trust">
                <div className="text-xs font-bold text-slate-900">Tenant-Isolated</div>
                <div className="text-[11px] text-slate-500">Atlas GridFS private storage</div>
              </div>
            </div>
          </div>

          {/* THE SIGNATURE HERO WORKSPACE COMPOSITION (Visual Proof of Product) */}
          <div className="hero-signature-workspace relative mx-auto max-w-5xl">
            {/* Floating Chip 1: Top-Right (Verbatim Substring Grounded) */}
            <div
              ref={badgeTopRef}
              className="hero-float-badge absolute -top-5 right-2 sm:right-6 z-30 hidden sm:flex items-center gap-2 rounded-xl bg-slate-900 text-white px-3.5 py-2 shadow-lg border border-slate-800 pointer-events-none"
            >
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[11px] font-semibold tracking-wide">
                Verbatim Substring Verified
              </span>
            </div>

            {/* Floating Chip 2: Bottom-Left (Zero Proportionate Deduction Risk) */}
            <div
              ref={badgeBottomRef}
              className="hero-float-badge absolute -bottom-5 left-2 sm:left-6 z-30 hidden sm:flex items-center gap-2 rounded-xl bg-white text-emerald-800 px-3.5 py-2 shadow-lg border border-emerald-200 pointer-events-none"
            >
              <CheckCircle2 className="h-4 w-4 text-emerald-600" />
              <span className="text-[11px] font-bold">
                Zero Proportionate Deduction Risk
              </span>
            </div>

            {/* Main Interactive Intelligence Desk Canvas */}
            <div
              ref={heroCardRef}
              className="relative rounded-2xl border border-slate-200/90 bg-white p-5 sm:p-7 shadow-[0_16px_50px_rgb(0,0,0,0.08)] hover:shadow-[0_24px_60px_rgb(0,0,0,0.12)] transition-shadow duration-300 md:animate-float-gentle"
            >
              {/* Document Window Header */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3.5 mb-5">
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900">
                        Care Health Advantage Policy Schedule
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded">
                        UIN: CHI-HLT-2024-V2
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-500">
                      Sum Insured: ₹5,00,000 &bull; Page 14 of 48 &bull; Verified
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 border border-emerald-200 flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                    Live Grounding Engine
                  </span>
                  <span className="hidden sm:inline-block text-[10px] font-mono text-slate-400">
                    Chunk #CC-08
                  </span>
                </div>
              </div>

              {/* Two-Column Structured Policy Analysis Layout */}
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-stretch">
                {/* Left Column: Authentic Policy Document Excerpt with Active Clause Highlight */}
                <div className="lg:col-span-6 rounded-xl border border-slate-200 bg-slate-50/70 p-4 space-y-3 font-sans">
                  <div className="flex items-center justify-between border-b border-slate-200/80 pb-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Section 3.1 &bull; In-Patient Hospitalization
                    </span>
                    <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200">
                      Page 14
                    </span>
                  </div>

                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    3.1(a) Hospital expenses incurred for day care procedures and inpatient
                    admissions exceeding 24 hours are payable as specified in the schedule of
                    benefits.
                  </p>

                  {/* Highlighted Clause Ribbon */}
                  <div className="rounded-lg bg-amber-50/90 border-l-4 border-l-amber-500 p-3 shadow-2xs">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[10px] font-bold text-amber-900 uppercase tracking-wider">
                        Extracted Condition 3.1(b)
                      </span>
                      <span className="text-[10px] font-semibold text-amber-800 bg-amber-100/80 px-1.5 py-0.2 rounded">
                        100% Substring Match
                      </span>
                    </div>
                    <p className="text-xs font-mono text-slate-800 italic leading-relaxed">
                      &ldquo;In-patient care room rent is payable up to Single Private A/C Room
                      category without co-payment or daily monetary ceiling. No proportionate
                      deduction shall be levied on associate medical fees.&rdquo;
                    </p>
                  </div>

                  <p className="text-[11px] text-slate-500 leading-relaxed">
                    3.1(c) Pre-hospitalization medical expenses for up to 30 days and
                    post-hospitalization follow-up for 60 days shall be admissible.
                  </p>
                </div>

                {/* Right Column: Visual Explanation & Grounded Consequence */}
                <div className="lg:col-span-6 rounded-xl border border-emerald-200/90 bg-emerald-50/40 p-4.5 flex flex-col justify-between space-y-3">
                  <div>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-[11px] font-bold text-slate-700">
                        Verified Plain-Language Outcome
                      </span>
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-600 px-2.5 py-0.5 text-[11px] font-semibold text-white shadow-2xs">
                        <CheckCircle2 className="h-3 w-3" />
                        Fully Covered
                      </span>
                    </div>

                    <div className="space-y-2 text-xs text-slate-700 leading-relaxed">
                      <p>
                        <strong>1. Room Rent Capping:</strong> You are entitled to choose any
                        standard Single Private A/C Room. There is <strong>no ₹5,000 daily limit</strong>.
                      </p>
                      <p>
                        <strong>2. Proportionate Deduction Penalty:</strong> Because room rent is not
                        subject to a monetary cap, your insurer cannot reduce payments for doctor
                        visits, anesthesia, nursing, or surgeon fees.
                      </p>
                    </div>

                    {/* Verbatim Citation Match Box */}
                    <div
                      ref={badgeRightRef}
                      className="mt-3 rounded-lg bg-white p-3 border border-emerald-200/90 shadow-2xs text-[11px] text-slate-600"
                    >
                      <div className="flex items-center justify-between text-emerald-800 font-semibold mb-1">
                        <span>Verbatim Citation Verification</span>
                        <span className="text-[10px] font-mono text-emerald-600">0 Tokens Injected</span>
                      </div>
                      <p className="italic text-slate-700">
                        &ldquo;...room rent is payable up to Single Private A/C Room without co-payment...&rdquo;
                      </p>
                      <div className="mt-1.5 flex items-center justify-between text-[10px] text-slate-400 font-mono pt-1.5 border-t border-slate-100">
                        <span>Document Coordinates: Page 14 &bull; Chunk #CC-08</span>
                        <span className="font-semibold text-emerald-700">Deterministic Match</span>
                      </div>
                    </div>
                  </div>

                  {/* Readiness Summary */}
                  <div className="flex items-center justify-between text-[11px] text-slate-500 pt-2 border-t border-emerald-100">
                    <span className="flex items-center gap-1.5 font-medium text-slate-700">
                      <Check className="h-3.5 w-3.5 text-emerald-600" />
                      Zero proportionate deduction exposure
                    </span>
                    <span className="font-semibold text-emerald-700">CoverScope Intelligence</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER A — THE PROBLEM (Section 4 Standard) */}
      {/* ===================================================================== */}
      <section id="problem" className="reveal-section py-20 bg-slate-900 text-white scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
            {/* Left: The Frustration Narrative */}
            <div className="lg:col-span-6 space-y-6">
              <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                Chapter A &bull; The Problem
              </span>
              <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl leading-tight">
                50 pages of fine print. <br />
                <span className="text-slate-400">One devastating surprise deduction.</span>
              </h2>
              <p className="text-sm sm:text-base text-slate-300 leading-relaxed">
                Health insurance policies in India are filled with complex interconnected terms. A
                simple clause buried on page 24 can reduce your claim settlement by hundreds of
                thousands of rupees.
              </p>

              <div className="space-y-3 pt-2 text-xs sm:text-sm text-slate-300">
                <div className="flex items-start gap-3">
                  <div className="h-5 w-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center shrink-0 mt-0.5">
                    <X className="h-3.5 w-3.5" />
                  </div>
                  <p>
                    <strong>The 1% Room Rent Trap:</strong> Exceeding your daily room limit triggers
                    proportionate deductions across all associated doctor and surgical charges.
                  </p>
                </div>

                <div className="flex items-start gap-3">
                  <div className="h-5 w-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center shrink-0 mt-0.5">
                    <X className="h-3.5 w-3.5" />
                  </div>
                  <p>
                    <strong>Hidden Waiting Clocks:</strong> Specific ailments (cataracts, hernia,
                    joint replacements) require 24 continuous months, even when accidental coverage
                    is active.
                  </p>
                </div>

                <div className="flex items-start gap-3">
                  <div className="h-5 w-5 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center shrink-0 mt-0.5">
                    <X className="h-3.5 w-3.5" />
                  </div>
                  <p>
                    <strong>Robotic &amp; Modern Caps:</strong> Advanced procedures often have discrete
                    sub-limits, leaving patients with massive out-of-pocket bills.
                  </p>
                </div>
              </div>
            </div>

            {/* Right: Tangible Comparison Card */}
            <div className="lg:col-span-6">
              <div className="rounded-2xl border border-slate-800 bg-slate-950 p-6 sm:p-8 space-y-5 shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">
                    Fine Print Reality Check
                  </span>
                  <span className="text-[11px] font-semibold text-rose-400 bg-rose-950/60 px-2 py-0.5 rounded border border-rose-800/40">
                    High Deduction Risk
                  </span>
                </div>

                <div className="space-y-3 text-xs">
                  <div className="rounded-xl bg-slate-900/90 border border-slate-800 p-3.5">
                    <span className="text-[10px] font-bold uppercase text-slate-500">
                      What the Policyholder Believed
                    </span>
                    <p className="text-slate-200 mt-1 font-medium">
                      &ldquo;My sum insured is ₹5,00,000. My laparoscopic surgery is ₹3,20,000. I am 100% covered.&rdquo;
                    </p>
                  </div>

                  <div className="rounded-xl bg-rose-950/20 border border-rose-900/40 p-3.5">
                    <span className="text-[10px] font-bold uppercase text-rose-400">
                      What Clause 3.1(b) Silently Enforced
                    </span>
                    <p className="text-slate-300 mt-1 leading-relaxed">
                      Because the patient stayed in a ₹8,000 room (above the ₹5,000 cap), the insurer
                      proportionately deducted 37.5% across surgeon fees, nursing, and OT charges.
                    </p>
                    <div className="mt-2 text-rose-300 font-bold flex items-center justify-between text-[11px] pt-2 border-t border-rose-900/40">
                      <span>Unexpected Out-of-Pocket Penalty:</span>
                      <span>₹54,000</span>
                    </div>
                  </div>
                </div>

                <p className="text-[11px] text-slate-500 italic">
                  CoverScope identifies these contractual landmines before admission so you can avoid deductions.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER B — THE TRANSFORMATION (Signature Clause Grounding) */}
      {/* ===================================================================== */}
      <section
        id="transformation"
        className="reveal-section py-20 bg-gradient-to-b from-white to-slate-50/70 border-b border-slate-200/80 scroll-mt-20"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 mb-2 border border-emerald-200">
              <Zap className="h-3.5 w-3.5 text-emerald-600" />
              <span>Chapter B &bull; The Transformation</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              From contract clause to actionable clarity
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-2">
              Watch how CoverScope extracts an obscure contractual condition, verifies its exact
              substring integrity, and translates it into financial consequence.
            </p>
          </div>

          <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs">
            {/* Step Controls */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4 border-b border-slate-100 pb-5 mb-6">
              <div className="flex items-center gap-2">
                {[
                  { step: 1, label: '1. Raw Schedule Clause' },
                  { step: 2, label: '2. Substring Verification' },
                  { step: 3, label: '3. Financial Consequence' },
                ].map((s) => (
                  <button
                    key={s.step}
                    type="button"
                    onClick={() => {
                      setIsWalkthroughPlaying(false);
                      setClauseWalkthroughStep(s.step);
                    }}
                    className={`rounded-lg px-3.5 py-1.5 text-xs font-semibold transition active:scale-[0.98] cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                      clauseWalkthroughStep === s.step
                        ? 'bg-slate-900 text-white shadow-xs ring-2 ring-slate-900/20'
                        : 'bg-slate-100 text-slate-600 hover:bg-slate-200/70 hover:text-slate-900'
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>

              <button
                type="button"
                onClick={handleStartWalkthrough}
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 hover:text-emerald-800 bg-emerald-50 hover:bg-emerald-100/70 active:scale-[0.98] px-3.5 py-1.5 rounded-lg border border-emerald-200 transition focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500"
              >
                <RotateCcw
                  className={`h-3.5 w-3.5 ${isWalkthroughPlaying ? 'animate-spin' : ''}`}
                />
                <span>{isWalkthroughPlaying ? 'Playing Walkthrough...' : 'Auto Replay'}</span>
              </button>
            </div>

            {/* Interactive Step Showcase */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {/* Box 1: Raw Clause */}
              <div
                className={`rounded-xl p-4 border transition-all duration-300 ${
                  clauseWalkthroughStep === 1
                    ? 'border-emerald-500 ring-2 ring-emerald-500/25 bg-emerald-50/35 shadow-xs'
                    : clauseWalkthroughStep > 1
                    ? 'border-emerald-500/60 bg-emerald-50/20 shadow-2xs'
                    : 'border-slate-200 bg-slate-50/50 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Step 1: Document Text
                  </span>
                  <span className="text-[10px] font-mono text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded border border-emerald-200/60">
                    Page 14
                  </span>
                </div>
                <p className="text-xs text-slate-700 font-mono italic leading-relaxed">
                  &ldquo;Room rent is capped at 1% of Sum Insured. If admitted to higher category,
                  associated medical expenses shall be proportionately reduced.&rdquo;
                </p>
                <div className="mt-3 text-[10px] text-slate-400">Section 3.1 &bull; Chunk #RR-88</div>
              </div>

              {/* Box 2: Substring Gate */}
              <div
                className={`rounded-xl p-4 border transition-all duration-300 ${
                  clauseWalkthroughStep === 2
                    ? 'border-teal-500 ring-2 ring-teal-500/25 bg-teal-50/35 shadow-xs'
                    : clauseWalkthroughStep > 2
                    ? 'border-teal-500/60 bg-teal-50/20 shadow-2xs'
                    : 'border-slate-200 bg-slate-50/50 opacity-60'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Step 2: Verification Gate
                  </span>
                  <span className="text-[10px] font-semibold text-teal-700 bg-teal-50 px-1.5 py-0.5 rounded flex items-center gap-1 border border-teal-200/60">
                    <Check className="h-3 w-3" />
                    Passed
                  </span>
                </div>
                <div className="space-y-1.5 text-xs text-slate-700">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Exact Substring:</span>
                    <span className="font-semibold text-slate-900">100% Match</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Synthetic Check:</span>
                    <span className="font-semibold text-emerald-700">0 Injected Tokens</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Page Boundary:</span>
                    <span className="font-semibold text-slate-900">Validated</span>
                  </div>
                </div>
                <div className="mt-3 text-[10px] text-teal-700 font-medium">
                  Prevents LLM hallucination
                </div>
              </div>

              {/* Box 3: Plain Consequence */}
              <div
                className={`rounded-xl p-4 border transition-all duration-300 ${
                  clauseWalkthroughStep === 3
                    ? 'border-slate-800 ring-2 ring-emerald-500/40 bg-slate-900 text-white shadow-md'
                    : 'border-slate-200 bg-slate-50/50 opacity-60 text-slate-800'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider ${
                      clauseWalkthroughStep === 3 ? 'text-emerald-400' : 'text-slate-500'
                    }`}
                  >
                    Step 3: Financial Consequence
                  </span>
                  <span
                    className={`text-[10px] font-semibold px-1.5 py-0.5 rounded ${
                      clauseWalkthroughStep === 3
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    Actionable
                  </span>
                </div>
                <p
                  className={`text-xs leading-relaxed ${
                    clauseWalkthroughStep === 3 ? 'text-slate-200' : 'text-slate-600'
                  }`}
                >
                  If you pick an ₹8,000/day room on a ₹5 Lakh policy (limit ₹5,000/day), the insurer
                  will cut 37.5% from doctor and surgeon fees. You would pay ₹62,000 out-of-pocket.
                </p>
                <div
                  className={`mt-3 text-[10px] ${
                    clauseWalkthroughStep === 3 ? 'text-emerald-400' : 'text-slate-400'
                  }`}
                >
                  Advice: Request standard single room to eliminate liability
                </div>
              </div>
            </div>

            <p className="mt-5 text-[11px] text-slate-400 text-center">
              Sample walkthrough simulating CoverScope&apos;s anti-hallucination verification engine.
            </p>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER C — FOUR CORE PRODUCT CAPABILITIES */}
      {/* ===================================================================== */}
      <section id="capabilities" className="reveal-section py-20 lg:py-28 scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3 border border-emerald-200">
              <Layers className="h-3.5 w-3.5 text-emerald-600" />
              <span>Chapter C &bull; Product Capabilities</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              Four distinct ways to understand your policy
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-2 leading-relaxed">
              Explore our four core tools designed for complete contractual transparency.
            </p>
          </div>

          {/* Interactive Capability Tabs */}
          <div
            className="flex flex-wrap items-center justify-center gap-2 mb-8"
            role="tablist"
            aria-label="CoverScope Capabilities"
          >
            {[
              { id: 'explorer', name: 'Policy Explorer', icon: Search },
              { id: 'ask', name: 'Ask My Policy', icon: FileText },
              { id: 'scenarios', name: 'Scenario Analyzer', icon: Scale },
              { id: 'rehearsal', name: 'Claim Rehearsal', icon: ClipboardCheck },
            ].map((tab, idx) => {
              const Icon = tab.icon;
              const isActive = activeCapabilityTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  role="tab"
                  id={`tab-${tab.id}`}
                  aria-selected={isActive}
                  aria-controls={`panel-${tab.id}`}
                  onKeyDown={(e) => handleCapabilityTabKeyDown(e, idx)}
                  onClick={() =>
                    setActiveCapabilityTab(
                      tab.id as 'explorer' | 'ask' | 'scenarios' | 'rehearsal'
                    )
                  }
                  className={`flex items-center gap-2 rounded-xl px-4 py-2.5 text-xs font-semibold transition active:scale-[0.98] cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                    isActive
                      ? 'bg-emerald-600 text-white shadow-xs ring-2 ring-emerald-600/30'
                      : 'bg-white border border-slate-200/90 text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-2xs'
                  }`}
                >
                  <Icon className={`h-4 w-4 transition-colors ${isActive ? 'text-white' : 'text-slate-500'}`} />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </div>

          {/* Interactive Preview Canvas */}
          <div
            className="mx-auto max-w-4xl min-h-[310px] rounded-2xl border border-slate-200/90 bg-white p-6 sm:p-8 shadow-xs"
            role="tabpanel"
            id={`panel-${activeCapabilityTab}`}
            aria-labelledby={`tab-${activeCapabilityTab}`}
          >
            {activeCapabilityTab === 'explorer' && (
              <div className="space-y-6 animate-in fade-in-50 duration-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">
                      Policy Explorer — Clause Reader &amp; Navigator
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Navigate your original policy schedule with categorized tags and page markers.
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    Structured Clause View
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-700">
                      Benefits &amp; Caps Breakdown
                    </span>
                    <p className="font-semibold text-slate-800">
                      Section 3.1: Room Rent &amp; ICU Limits
                    </p>
                    <p className="text-slate-600 leading-relaxed text-[11px]">
                      Displays daily room rent ceilings, ICU limits, nursing fees, and attendant
                      allowance without manually combing through 45-page policy prospectuses.
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-700">
                      Waiting Period Matrix
                    </span>
                    <p className="font-semibold text-slate-800">
                      Section 4.1 to 4.4: Specific Ailment Schedule
                    </p>
                    <p className="text-slate-600 leading-relaxed text-[11px]">
                      Direct table view of 30-day initial moratorium, 24-month joint/hernia waiting
                      periods, and 36-month declared pre-existing illness thresholds.
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-slate-100/70 p-3 text-xs text-slate-600 flex items-center justify-between">
                  <span>Allows instant PDF download of the original document anytime.</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    PyMuPDF &bull; Categorized Chunks
                  </span>
                </div>
              </div>
            )}

            {activeCapabilityTab === 'ask' && (
              <div className="space-y-6 animate-in fade-in-50 duration-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">
                      Ask My Policy — Conversational Intelligence
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Natural language policy Q&amp;A backed by substring anti-hallucination checks.
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50 px-3 py-1 rounded-full border border-emerald-200">
                    <Shield className="h-3.5 w-3.5 text-emerald-600" />
                    Zero Synthetic Quotes
                  </span>
                </div>

                <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-4 space-y-3">
                  <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
                    <div className="h-6 w-6 rounded-full bg-emerald-600 text-white flex items-center justify-center text-[10px]">
                      Q
                    </div>
                    <span>
                      &ldquo;Is robotic cataract surgery covered, and what is the lens limit?&rdquo;
                    </span>
                  </div>

                  <div className="rounded-lg bg-white p-3.5 border border-emerald-200/70 text-xs text-slate-700 space-y-2">
                    <div className="flex items-center justify-between text-[11px] font-bold text-emerald-800">
                      <span>CoverScope Verified Answer</span>
                      <span>Page 19, Chunk #CAT-04</span>
                    </div>
                    <p className="text-[11px] leading-relaxed">
                      Cataract surgery is covered subject to a limit of ₹40,000 per eye. Robotic or
                      femtosecond laser-assisted procedures are payable within this sub-limit.
                      Multifocal or premium toric lenses beyond the monetary cap are payable out of
                      pocket.
                    </p>
                    <blockquote className="border-l-2 border-emerald-600 pl-2 text-[10px] italic text-slate-500">
                      &ldquo;Expenses for cataract treatment are limited to Rs. 40,000 per eye per
                      policy period...&rdquo;
                    </blockquote>
                  </div>
                </div>

                <div className="rounded-xl bg-slate-100/70 p-3 text-xs text-slate-600 flex items-center justify-between">
                  <span>Every answer includes a verbatim citation check before rendering.</span>
                  <span className="font-mono text-[10px] text-slate-400">Groq LLM + BM25 Gate</span>
                </div>
              </div>
            )}

            {activeCapabilityTab === 'scenarios' && (
              <div className="space-y-6 animate-in fade-in-50 duration-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">
                      Scenario Analyzer — Tenure &amp; Ailment Modeling
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Simulate concrete medical treatments against your active policy tenure.
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 bg-blue-50 px-3 py-1 rounded-full border border-blue-200">
                    <Scale className="h-3.5 w-3.5 text-blue-600" />
                    Deterministic Rule Clock
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1.5">
                    <span className="text-[10px] font-bold text-slate-500">Day 1 to 30</span>
                    <h4 className="font-bold text-slate-900">Initial Moratorium</h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Only accidental injuries covered. Non-emergency illnesses excluded.
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1.5">
                    <span className="text-[10px] font-bold text-amber-700">Month 1 to 24</span>
                    <h4 className="font-bold text-slate-900">Specific Conditions</h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Knee replacements, ENT surgeries, hernia, calculus stones waiting period.
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-3.5 space-y-1.5">
                    <span className="text-[10px] font-bold text-emerald-700">Month 36+</span>
                    <h4 className="font-bold text-slate-900">Full PED Coverage</h4>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Declared diabetes, asthma, hypertension fully eligible for cashless claims.
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-slate-100/70 p-3 text-xs text-slate-600 flex items-center justify-between">
                  <span>Includes scenario assessment history with timestamp tracking.</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    Standard IRDAI Regulations
                  </span>
                </div>
              </div>
            )}

            {activeCapabilityTab === 'rehearsal' && (
              <div className="space-y-6 animate-in fade-in-50 duration-200">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 border-b border-slate-100 pb-4">
                  <div>
                    <h3 className="text-lg font-bold text-slate-900">
                      Claim Rehearsal — Admission Simulation &amp; Checklists
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Simulate a planned hospital admission to compute financial liabilities before
                      billing.
                    </p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-purple-700 bg-purple-50 px-3 py-1 rounded-full border border-purple-200">
                    <ClipboardCheck className="h-3.5 w-3.5 text-purple-600" />
                    Financial Exposure Engine
                  </span>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                  <div className="rounded-xl border border-purple-100 bg-purple-50/30 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">Proportionate Deduction Audit</span>
                      <span className="text-[10px] font-semibold text-purple-700 bg-purple-100 px-2 py-0.5 rounded">
                        Simulated
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Detects if picking an Executive Suite on a ₹5 Lakh policy triggers reductions
                      on your anaesthetist, surgeon, and surgical equipment bills.
                    </p>
                  </div>

                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-900">TPA Readiness Checklist</span>
                      <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded">
                        Cashless Ready
                      </span>
                    </div>
                    <p className="text-[11px] text-slate-600 leading-relaxed">
                      Generates exact document checklists: ICP notes, pre-auth form, investigation
                      films, and pharmacy itemized receipts required for 48-hour approvals.
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-slate-100/70 p-3 text-xs text-slate-600 flex items-center justify-between">
                  <span>Revisit and inspect previous rehearsal runs anytime from your history.</span>
                  <span className="font-mono text-[10px] text-slate-400">
                    Tenant-isolated run history
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER D — FINANCIAL IMPLICATIONS CALCULATOR */}
      {/* ===================================================================== */}
      <section
        id="financial-impact"
        className="reveal-section py-20 bg-slate-50/70 border-y border-slate-200/80 scroll-mt-20"
      >
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3 border border-emerald-200">
              <Calculator className="h-3.5 w-3.5 text-emerald-600" />
              <span>Chapter D &bull; Financial Impact</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              Why fine print matters in Rupees
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-2 leading-relaxed">
              Explore how choosing a room above your daily monetary limit silently escalates your
              out-of-pocket costs on associate doctor and surgery bills.
            </p>
          </div>

          <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white p-6 sm:p-8 shadow-xs space-y-6">
            {/* Bill Amount Selector */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-100 pb-5">
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                  Simulate Planned Hospital Stay (₹5L Policy)
                </span>
                <p className="text-sm font-bold text-slate-900">
                  Total Bill Estimate:{' '}
                  <span className="text-emerald-700">₹{simulatedBillAmount.toLocaleString('en-IN')}</span>
                </p>
              </div>

              <div className="flex items-center gap-2">
                {[200000, 400000, 600000].map((amt) => (
                  <button
                    key={amt}
                    type="button"
                    onClick={() => setSimulatedBillAmount(amt)}
                    className={`px-3.5 py-1.5 rounded-xl text-xs font-semibold transition active:scale-[0.97] cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 ${
                      simulatedBillAmount === amt
                        ? 'bg-slate-900 text-white shadow-xs ring-2 ring-slate-900/20'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200/80 hover:text-slate-900'
                    }`}
                  >
                    ₹{(amt / 100000).toFixed(0)} Lakh
                  </button>
                ))}
              </div>
            </div>

            {/* Plan A vs Plan B Financial Comparison */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5 text-xs">
              {/* Plan A: With 1% Room Rent Cap */}
              <div className="rounded-xl border border-rose-200/90 bg-rose-50/30 p-5 space-y-3 transition-shadow duration-200 hover:shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900">Plan A: 1% Room Rent Limit</span>
                  <span className="text-[10px] font-bold text-rose-700 bg-rose-100 px-2 py-0.5 rounded border border-rose-200/60">
                    High Out-of-Pocket
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Admitted to ₹8,000/day room with a ₹5,000 daily cap. Triggers 37.5% proportionate
                  deduction on surgeon, OT, and medical fees.
                </p>

                <div className="rounded-lg bg-white p-3 border border-rose-200/80 space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-500">Insurer Settlement:</span>
                    <span className="font-semibold text-slate-800 tabular-nums">
                      ₹{(simulatedBillAmount - planAOutOfPocket).toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs font-bold text-rose-700 pt-1 border-t border-slate-100">
                    <span>You Pay Out-of-Pocket:</span>
                    <span className="tabular-nums">₹{planAOutOfPocket.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>

              {/* Plan B: Single Private AC Room with No Cap */}
              <div className="rounded-xl border border-emerald-200/90 bg-emerald-50/40 p-5 space-y-3 transition-shadow duration-200 hover:shadow-2xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-slate-900">Plan B: Single AC Room (No Cap)</span>
                  <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded border border-emerald-200/60">
                    Zero Deductions
                  </span>
                </div>
                <p className="text-[11px] text-slate-600 leading-relaxed">
                  Admitted to standard Single Private AC Room. No monetary ceiling applies, so no
                  proportionate reductions are levied on associated bills.
                </p>

                <div className="rounded-lg bg-white p-3 border border-emerald-200/80 space-y-1.5">
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-500">Insurer Settlement:</span>
                    <span className="font-semibold text-slate-800 tabular-nums">
                      ₹{simulatedBillAmount.toLocaleString('en-IN')}
                    </span>
                  </div>
                  <div className="flex justify-between text-xs font-bold text-emerald-700 pt-1 border-t border-slate-100">
                    <span>You Pay Out-of-Pocket:</span>
                    <span className="tabular-nums">₹{planBOutOfPocket.toLocaleString('en-IN')}</span>
                  </div>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-400 text-center">
              Illustrative financial model based on standard proportionate deduction math. Actual
              settlements depend on individual hospital itemized bills and policy wording.
            </p>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER E — THREE-STEP WORKFLOW */}
      {/* ===================================================================== */}
      <section id="workflow" className="reveal-section py-20 bg-slate-900 text-white scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <span className="text-xs font-semibold uppercase tracking-wider text-emerald-400">
              Chapter E &bull; Three-Step Workflow
            </span>
            <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl mt-2">
              From PDF schedule to actionable clarity
            </h2>
            <p className="text-xs sm:text-sm text-slate-400 mt-2 leading-relaxed">
              No generic chatbot generalizations. Real document intelligence in three steps.
            </p>
          </div>

          <div className="stagger-grid grid grid-cols-1 md:grid-cols-3 gap-8 relative">
            {/* Step 1 */}
            <CardTilt
              className="stagger-card rounded-2xl border border-slate-800 bg-slate-950/70 p-6 relative hover:border-emerald-500/50 hover:bg-slate-950"
              maxTilt={6}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="text-3xl font-black text-emerald-500/40">01</div>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-950/80 text-emerald-400 border border-emerald-800/40">
                  <FileText className="h-4 w-4" />
                </div>
              </div>
              <h3 className="text-base font-bold text-white">Upload Policy Document</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Upload your official PDF policy schedule or prospectus. Files are stored securely in
                MongoDB Atlas GridFS, strictly isolated to your authenticated tenant.
              </p>
            </CardTilt>

            {/* Step 2 */}
            <CardTilt
              className="stagger-card rounded-2xl border border-slate-800 bg-slate-950/70 p-6 relative hover:border-emerald-500/50 hover:bg-slate-950"
              maxTilt={6}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="text-3xl font-black text-emerald-500/40">02</div>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-950/80 text-teal-400 border border-teal-800/40">
                  <Search className="h-4 w-4" />
                </div>
              </div>
              <h3 className="text-base font-bold text-white">Clause Ingestion &amp; Indexing</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                PyMuPDF extracts raw pages and indexes benefits, waiting periods, room categories,
                and exclusions into BM25 chunks with verified page coordinates.
              </p>
            </CardTilt>

            {/* Step 3 */}
            <CardTilt
              className="stagger-card rounded-2xl border border-slate-800 bg-slate-950/70 p-6 relative hover:border-emerald-500/50 hover:bg-slate-950"
              maxTilt={6}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="text-3xl font-black text-emerald-500/40">03</div>
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-950/80 text-purple-400 border border-purple-800/40">
                  <CheckCircle2 className="h-4 w-4" />
                </div>
              </div>
              <h3 className="text-base font-bold text-white">Grounded Verification</h3>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Consult your policy schedule, simulate planned treatments, and inspect verbatim
                clauses before submitting pre-authorization requests to your TPA.
              </p>
            </CardTilt>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER F — TRUST & ETHICAL BOUNDARIES */}
      {/* ===================================================================== */}
      <section id="trust" className="reveal-section py-20 bg-white scroll-mt-20">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl border border-slate-200 bg-slate-50/60 p-8 sm:p-12 shadow-xs">
            <div className="max-w-3xl mx-auto space-y-6 text-center">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">
                <Shield className="h-3.5 w-3.5 text-emerald-700" />
                <span>Chapter F &bull; Trust &amp; Boundaries</span>
              </div>

              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">
                Honest technology, clearly communicated boundaries
              </h2>

              <p className="text-xs sm:text-sm text-slate-600 leading-relaxed">
                CoverScope is built to provide transparency into insurance fine print. We adhere to
                strict engineering guardrails so you know what is grounded in text and what requires
                confirmation with your insurer.
              </p>

              <div className="stagger-grid grid grid-cols-1 sm:grid-cols-3 gap-4 text-left text-xs pt-4">
                <CardTilt
                  className="stagger-card rounded-xl bg-white p-4.5 border border-slate-200/80 shadow-2xs"
                  maxTilt={5}
                >
                  <h4 className="font-bold text-slate-900 mb-1">Verbatim Proof</h4>
                  <p className="text-slate-500 leading-relaxed">
                    Answers must quote authentic document chunks. If evidence is inconclusive,
                    CoverScope explicitly flags it.
                  </p>
                </CardTilt>

                <CardTilt
                  className="stagger-card rounded-xl bg-white p-4.5 border border-slate-200/80 shadow-2xs"
                  maxTilt={5}
                >
                  <h4 className="font-bold text-slate-900 mb-1">Tenant Privacy</h4>
                  <p className="text-slate-500 leading-relaxed">
                    Documents are private to your user ID. User A cannot access, query, or delete
                    User B&apos;s policies or chat histories.
                  </p>
                </CardTilt>

                <CardTilt
                  className="stagger-card rounded-xl bg-white p-4.5 border border-slate-200/80 shadow-2xs"
                  maxTilt={5}
                >
                  <h4 className="font-bold text-slate-900 mb-1">Not Insurance Advice</h4>
                  <p className="text-slate-500 leading-relaxed">
                    CoverScope is an educational and analytical tool. Formal claims are adjudicated
                    by your insurance company and licensed TPA.
                  </p>
                </CardTilt>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* FAQ SECTION */}
      {/* ===================================================================== */}
      <section id="faq" className="reveal-section py-20 bg-slate-50/70 border-t border-slate-200/80 scroll-mt-20">
        <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-14">
            <div className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-800 mb-3 border border-emerald-200">
              <HelpCircle className="h-3.5 w-3.5 text-emerald-600" />
              <span>Frequently Asked Questions</span>
            </div>
            <h2 className="text-3xl font-extrabold tracking-tight text-slate-900 sm:text-4xl">
              Clear answers about our technology
            </h2>
            <p className="text-xs sm:text-sm text-slate-500 mt-2 leading-relaxed">
              Everything you need to know about CoverScope&apos;s architecture, limitations, and
              privacy protections.
            </p>
          </div>

          <div className="space-y-3.5">
            {FAQS.map((faq) => {
              const isOpen = openFaqId === faq.id;
              return (
                <div
                  key={faq.id}
                  className="rounded-2xl border border-slate-200 bg-white transition-all duration-200 overflow-hidden shadow-2xs hover:border-slate-300"
                >
                  <button
                    type="button"
                    onClick={() => setOpenFaqId(isOpen ? null : faq.id)}
                    aria-expanded={isOpen}
                    aria-controls={`faq-answer-${faq.id}`}
                    className="w-full text-left px-5 py-4 flex items-center justify-between gap-4 font-semibold text-sm text-slate-900 cursor-pointer focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500"
                  >
                    <span>{faq.question}</span>
                    <ChevronDown
                      className={`h-4 w-4 text-slate-400 shrink-0 transition-transform duration-200 ${
                        isOpen ? 'rotate-180 text-emerald-600' : ''
                      }`}
                    />
                  </button>

                  {isOpen && (
                    <div
                      id={`faq-answer-${faq.id}`}
                      className="px-5 pb-5 pt-1 text-xs sm:text-sm text-slate-600 leading-relaxed border-t border-slate-100 bg-slate-50/40 animate-in fade-in-50 duration-150"
                    >
                      {faq.answer}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* CHAPTER G — THE SIGNATURE FINAL CTA */}
      {/* ===================================================================== */}
      <section id="cta" className="reveal-section py-20 bg-slate-950 text-white text-center relative overflow-hidden">
        {/* Subtle ambient light */}
        <div className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-96 w-96 rounded-full bg-emerald-500/15 blur-3xl" />

        <div className="relative mx-auto max-w-4xl px-4 sm:px-6 lg:px-8 space-y-6">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-950/60 px-4 py-1 text-xs font-semibold text-emerald-400">
            <span>CoverScope Intelligence</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl lg:text-5xl">
            Bring clarity to your health insurance policy
          </h2>
          <p className="text-xs sm:text-sm text-slate-400 max-w-xl mx-auto leading-relaxed">
            Create an account in seconds to upload your policy schedule, explore hidden sub-limits,
            and simulate medical claims with zero guesswork.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-4">
            <Link
              to={isAuthenticated ? '/dashboard' : '/register'}
              className="group w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-7 py-3.5 text-sm sm:text-base font-semibold text-white shadow-xs hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
            >
              <span>{isAuthenticated ? 'Go to Dashboard' : 'Explore your policy free'}</span>
              <ArrowRight className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1" />
            </Link>

            <Link
              to="/login"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl border border-slate-800 bg-slate-900 px-6 py-3.5 text-sm sm:text-base font-semibold text-slate-300 hover:bg-slate-800 hover:text-white active:scale-[0.98] transition duration-150 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-slate-500"
            >
              <span>Sign in to existing workspace</span>
            </Link>
          </div>
        </div>
      </section>

      {/* ===================================================================== */}
      {/* INSTITUTIONAL PROFESSIONAL FOOTER                                     */}
      {/* ===================================================================== */}
      <Footer isLanding={true} />
    </div>
  );
};
