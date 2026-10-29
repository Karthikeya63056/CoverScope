import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  ShieldCheck,
  CheckCircle2,
  ArrowRight,
  ArrowUp,
  Sparkles,
  Database,
  Lock,
  FileText,
  ClipboardCheck,
  Scale,
  GitCompare,
  Search,
  Activity,
  Send,
  Check,
  ExternalLink,
  ChevronRight,
  FileCheck,
} from 'lucide-react';
import { CardTilt } from './CardTilt';

interface FooterProps {
  isLanding?: boolean;
}

export const Footer: React.FC<FooterProps> = ({ isLanding = false }) => {
  const [email, setEmail] = useState('');
  const [subscribed, setSubscribed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubscribe = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes('@')) return;
    setIsSubmitting(true);
    setTimeout(() => {
      setIsSubmitting(false);
      setSubscribed(true);
      setEmail('');
    }, 450);
  };

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: 'smooth',
    });
  };

  return (
    <footer className="relative mt-auto border-t border-slate-800 bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-400 overflow-hidden">
      {/* ===================================================================== */}
      {/* ATMOSPHERIC AMBIENT GLOW BACKDROP                                     */}
      {/* ===================================================================== */}
      <div
        className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 h-full w-full max-w-7xl -z-10 overflow-hidden"
        aria-hidden="true"
      >
        <div className="absolute -top-24 right-1/4 h-80 w-80 rounded-full bg-emerald-500/10 blur-3xl animate-glow-shift" />
        <div className="absolute top-1/2 left-1/4 h-96 w-96 rounded-full bg-teal-500/10 blur-3xl animate-pulse-ambient" />
      </div>

      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 pt-12 pb-8">
        {/* =================================================================== */}
        {/* 1. TOP INTERACTIVE PRE-FOOTER BANNER                                */}
        {/* =================================================================== */}
        <div className="mb-12">
          <CardTilt
            maxTilt={3}
            spotlightColor="rgba(16, 185, 129, 0.12)"
            className="relative rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900/90 via-slate-900/70 to-slate-950/90 p-6 sm:p-8 backdrop-blur-md shadow-xl"
          >
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
              <div className="space-y-2 max-w-2xl">
                <div className="inline-flex items-center gap-2 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                  <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
                  <span>Flagship Claim Simulation Workspace</span>
                </div>
                <h3 className="text-lg sm:text-xl font-extrabold text-white tracking-tight">
                  Stress-test hospital admission before pre-auth submission
                </h3>
                <p className="text-xs sm:text-sm text-slate-400 leading-relaxed">
                  Compute room-rent proportionate deductions, validate pre-existing condition waiting
                  clocks, and generate an actionable claim checklist directly from your policy schedule.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3 shrink-0">
                <Link
                  to="/claim-rehearsal"
                  className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-5 py-2.5 sm:py-3 text-xs sm:text-sm font-bold text-slate-950 shadow-md hover:bg-emerald-400 transition-all active:scale-98"
                >
                  <ClipboardCheck className="h-4 w-4" />
                  <span>Start Claim Rehearsal</span>
                  <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  to="/library"
                  className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2.5 sm:py-3 text-xs sm:text-sm font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-all active:scale-98"
                >
                  <FileText className="h-4 w-4 text-emerald-400" />
                  <span>Document Library</span>
                </Link>
              </div>
            </div>
          </CardTilt>
        </div>

        {/* =================================================================== */}
        {/* 2. MAIN 5-COLUMN INSTITUTIONAL NAVIGATION GRID                      */}
        {/* =================================================================== */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-12 gap-8 lg:gap-10 pb-12 border-b border-slate-800/80">
          {/* Column 1: Brand & Institutional Identity (4 cols) */}
          <div className="lg:col-span-4 space-y-4">
            <Link to={isLanding ? '/' : '/dashboard'} className="inline-flex items-center gap-3 group">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 text-slate-950 shadow-md group-hover:scale-105 transition-transform duration-200">
                <Shield className="h-5 w-5 font-bold" />
              </div>
              <div>
                <span className="text-xl font-extrabold tracking-tight text-white group-hover:text-emerald-400 transition-colors">
                  Cover<span className="text-emerald-400">Scope</span>
                </span>
                <span className="block text-[10px] font-semibold uppercase tracking-wider text-slate-400 -mt-1">
                  Your Policy. Made Clear.
                </span>
              </div>
            </Link>

            <p className="text-xs text-slate-400 leading-relaxed pr-4">
              Deterministic health insurance intelligence workspace designed for policyholders and
              advisors. Interrogate complex clauses, compute proportionate deductions, and eliminate
              hospitalization surprises with verbatim page-grounded citations.
            </p>

            {/* Operational Status Pill */}
            <div className="inline-flex items-center gap-2 rounded-full bg-slate-900 border border-slate-800 px-3 py-1 text-[11px] text-slate-300">
              <span className="flex h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span className="font-semibold text-white">All 5 Intelligence Engines Operational</span>
            </div>

            {/* Compliance & Security Pills */}
            <div className="flex flex-wrap gap-2 pt-1">
              <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-900/90 border border-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">
                <Lock className="h-3 w-3 text-emerald-400" />
                PBKDF2 Encrypted
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-900/90 border border-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">
                <Database className="h-3 w-3 text-teal-400" />
                MongoDB Atlas Sync
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-900/90 border border-slate-800 px-2.5 py-1 text-[10px] font-semibold text-slate-300">
                <ShieldCheck className="h-3 w-3 text-emerald-400" />
                IRDAI Health 2024
              </span>
            </div>
          </div>

          {/* Column 2: Intelligence Engines (2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <Activity className="h-3.5 w-3.5 text-emerald-400" />
              <span>Core Engines</span>
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link
                  to="/claim-rehearsal"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Claim Rehearsal</span>
                  <span className="rounded bg-emerald-500/20 text-emerald-300 px-1 py-0.2 text-[9px] font-bold">
                    NEW
                  </span>
                </Link>
              </li>
              <li>
                <Link
                  to="/ask"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Ask My Policy</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/scenarios"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Scenario Analyzer</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/compare"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Policy Comparison</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/explorer"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Policy Explorer</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 3: Grounded Audits (2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <Scale className="h-3.5 w-3.5 text-teal-400" />
              <span>Grounded Audits</span>
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link
                  to="/claim-rehearsal"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Room Rent Deductions</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/scenarios"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>PED Waiting Period</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/claim-rehearsal"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Co-Payment Exposure</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/explorer"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Day-Care &amp; Robotic Ops</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/claim-rehearsal"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Pre-Auth Checklist</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 4: Platform Workspace (2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <FileCheck className="h-3.5 w-3.5 text-blue-400" />
              <span>Workspace</span>
            </h4>
            <ul className="space-y-2 text-xs">
              <li>
                <Link
                  to="/dashboard"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Command Center</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/library"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Schedule Library</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/dashboard"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Evidence Studio</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/library"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Upload Policy PDF</span>
                </Link>
              </li>
              <li>
                <Link
                  to="/dashboard"
                  className="hover:text-emerald-400 transition-colors inline-flex items-center gap-1.5 group"
                >
                  <ChevronRight className="h-3 w-3 text-slate-600 group-hover:text-emerald-400 group-hover:translate-x-0.5 transition-all" />
                  <span>Telemetry Dossier</span>
                </Link>
              </li>
            </ul>
          </div>

          {/* Column 5: Regulatory Pulse & Policy Alerts (2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-white flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-amber-400" />
              <span>Policy Pulse</span>
            </h4>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Receive alerts on IRDAI waiting period standardizations and room-rent sublimit amendments.
            </p>

            {subscribed ? (
              <div className="rounded-lg bg-emerald-500/10 border border-emerald-500/30 p-2.5 text-[11px] text-emerald-300 flex items-center gap-2">
                <Check className="h-4 w-4 text-emerald-400 shrink-0" />
                <span>Subscribed! Grounded alerts enabled.</span>
              </div>
            ) : (
              <form onSubmit={handleSubscribe} className="space-y-1.5">
                <div className="relative">
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@domain.com"
                    aria-label="Email for policy alerts"
                    required
                    className="w-full rounded-lg border border-slate-700 bg-slate-900/90 py-1.5 pl-3 pr-8 text-xs text-white placeholder-slate-500 focus:border-emerald-500 focus:outline-hidden focus:ring-1 focus:ring-emerald-500/30 transition"
                  />
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    aria-label="Submit subscription"
                    className="absolute right-1 top-1/2 -translate-y-1/2 p-1 text-slate-400 hover:text-emerald-400 transition disabled:opacity-50"
                  >
                    <Send className="h-3.5 w-3.5" />
                  </button>
                </div>
                <span className="block text-[10px] text-slate-500">
                  Zero spam. Deterministic alerts only.
                </span>
              </form>
            )}
          </div>
        </div>

        {/* =================================================================== */}
        {/* 3. BOTTOM INSTITUTIONAL LEGAL & UTILITY STRIP                       */}
        {/* =================================================================== */}
        <div className="pt-8 flex flex-col md:flex-row md:items-center md:justify-between gap-6 text-[11px] text-slate-500">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2 text-slate-400">
              <span className="font-semibold text-white">&copy; {new Date().getFullYear()} CoverScope Technologies Inc.</span>
              <span>•</span>
              <span>All rights reserved.</span>
              <span>•</span>
              <span className="text-emerald-400 font-medium">IRDAI Standardized Health Schedule Engine</span>
            </div>
            <p className="max-w-2xl text-[10px] text-slate-500 leading-relaxed">
              CoverScope provides deterministic document intelligence and computational simulation based on
              uploaded policy contract schedules. It does not sell insurance policies, underwrite health risks,
              or guarantee claim approvals. Always verify planned hospital admissions directly with your insurer
              or authorized Third Party Administrator (TPA).
            </p>
          </div>

          <div className="flex items-center gap-4 shrink-0">
            {isLanding && (
              <div className="hidden sm:flex items-center gap-3 text-slate-400">
                <a href="#problem" className="hover:text-emerald-400 transition-colors">
                  Problem
                </a>
                <a href="#transformation" className="hover:text-emerald-400 transition-colors">
                  Grounding
                </a>
                <a href="#capabilities" className="hover:text-emerald-400 transition-colors">
                  Features
                </a>
                <a href="#faq" className="hover:text-emerald-400 transition-colors">
                  FAQ
                </a>
              </div>
            )}

            {/* Back to Top Smooth Trigger */}
            <button
              onClick={scrollToTop}
              title="Scroll back to top"
              className="inline-flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/90 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:border-emerald-500/50 hover:bg-slate-800 hover:text-white transition-all active:scale-95 shadow-sm group"
            >
              <span>Back to Top</span>
              <ArrowUp className="h-3.5 w-3.5 text-emerald-400 group-hover:-translate-y-0.5 transition-transform" />
            </button>
          </div>
        </div>
      </div>
    </footer>
  );
};
