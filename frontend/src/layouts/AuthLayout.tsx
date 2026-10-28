import React from 'react';
import { Shield, FileCheck, CheckCircle2, Sparkles, Lock, ArrowUpRight } from 'lucide-react';

interface AuthLayoutProps {
  children: React.ReactNode;
  title: string;
  subtitle: string;
  alternateAction: React.ReactNode;
}

export const AuthLayout: React.FC<AuthLayoutProps> = ({
  children,
  title,
  subtitle,
  alternateAction,
}) => {
  return (
    <div className="flex min-h-screen w-full bg-[#f8faf9] text-slate-900 antialiased font-sans selection:bg-emerald-100 selection:text-emerald-900">
      {/* ========================================================================= */}
      {/* DESKTOP BRANDING & PRODUCT INTELLIGENCE PANEL (Left 50-52%) */}
      {/* ========================================================================= */}
      <div className="relative hidden w-1/2 flex-col justify-between overflow-hidden bg-[#09111e] p-12 text-white lg:flex xl:p-16 border-r border-slate-800/60">
        {/* Subtle geometric grid background overlay */}
        <div 
          className="pointer-events-none absolute inset-0 opacity-[0.035]"
          style={{
            backgroundImage: `radial-gradient(rgba(255, 255, 255, 0.4) 1px, transparent 1px)`,
            backgroundSize: '24px 24px',
          }}
        />

        {/* Ambient emerald & teal gradient glow */}
        <div className="pointer-events-none absolute -top-32 -left-32 h-[480px] w-[480px] rounded-full bg-emerald-500/10 blur-[120px]" />
        <div className="pointer-events-none absolute -bottom-32 -right-32 h-[480px] w-[480px] rounded-full bg-teal-500/10 blur-[120px]" />

        {/* Top Header: Identity & Tagline */}
        <div className="relative z-10 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 text-slate-950 shadow-md shadow-emerald-500/20">
              <Shield className="h-5 w-5 text-slate-950 stroke-[2.4]" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <span className="text-xl font-bold tracking-tight text-white">CoverScope</span>
                <span className="rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300 border border-emerald-500/30">
                  Intelligence
                </span>
              </div>
              <p className="text-xs text-slate-400 font-medium tracking-wide">
                Your policy. Made clear.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 text-[11px] text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded-full border border-slate-800">
            <Lock className="h-3 w-3 text-emerald-400" />
            <span>Tenant Isolated</span>
          </div>
        </div>

        {/* Center: Core Value Proposition & Interactive Policy Evidence Preview */}
        <div className="relative z-10 my-auto py-8 max-w-xl">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-500/25 bg-emerald-950/60 px-3 py-1 text-xs font-semibold text-emerald-300 backdrop-blur-md">
            <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
            <span>Evidence-Grounded Policy Intelligence</span>
          </div>

          <h1 className="text-3xl font-extrabold tracking-tight text-white sm:text-4xl leading-[1.2] mb-4">
            Health insurance terms,{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-300">
              verified down to the clause.
            </span>
          </h1>

          <p className="text-sm text-slate-300 leading-relaxed mb-8 max-w-lg">
            CoverScope indexes your complete policy document with strict anti-hallucination guardrails,
            answering questions and simulating hospitalization claims with exact page citations.
          </p>

          {/* Authentic CoverScope Policy Evidence Citation Card */}
          <div className="relative rounded-2xl border border-slate-700/70 bg-gradient-to-b from-slate-900/90 to-slate-900/60 p-5 shadow-2xl backdrop-blur-md">
            {/* Card Header */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3.5">
              <div className="flex items-center gap-2">
                <FileCheck className="h-4 w-4 text-emerald-400" />
                <span className="text-xs font-semibold text-slate-200">
                  Comprehensive Health Care Policy &bull; Section 3.2
                </span>
              </div>
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="h-3 w-3" />
                Verified Clause
              </span>
            </div>

            {/* Verbatim Clause Citation */}
            <blockquote className="rounded-xl bg-slate-950/80 p-3.5 border border-slate-800 text-xs text-slate-300 leading-relaxed font-sans italic border-l-2 border-l-emerald-500">
              &ldquo;Room rent and boarding expenses are indemnified up to the Single Private A/C Room
              category with no proportionate deduction on diagnostic or surgeon fees.&rdquo;
            </blockquote>

            {/* Evidence Metadata Footer */}
            <div className="mt-3.5 flex items-center justify-between text-[11px] text-slate-400">
              <div className="flex items-center gap-2">
                <span className="rounded-md bg-slate-800 px-2 py-0.5 font-medium text-slate-300">
                  Page 18 &bull; Chunk #PED-04
                </span>
                <span className="text-emerald-400 font-semibold">100% Verbatim Match</span>
              </div>
              <span className="text-slate-500 text-[10px]">Zero Hallucination Gate</span>
            </div>
          </div>

          {/* Three Concise Feature Pillars */}
          <div className="mt-8 grid grid-cols-3 gap-3 text-xs">
            <div className="rounded-xl border border-slate-800/90 bg-slate-900/40 p-3 backdrop-blur-xs">
              <p className="font-semibold text-slate-200 mb-0.5">Exact Citations</p>
              <p className="text-[11px] text-slate-400 leading-normal">
                Every answer references authentic policy pages and terms.
              </p>
            </div>
            <div className="rounded-xl border border-slate-800/90 bg-slate-900/40 p-3 backdrop-blur-xs">
              <p className="font-semibold text-slate-200 mb-0.5">Claim Rehearsal</p>
              <p className="text-[11px] text-slate-400 leading-normal">
                Simulate admissions to reveal rent caps and co-pays.
              </p>
            </div>
            <div className="rounded-xl border border-slate-800/90 bg-slate-900/40 p-3 backdrop-blur-xs">
              <p className="font-semibold text-slate-200 mb-0.5">Waiting Periods</p>
              <p className="text-[11px] text-slate-400 leading-normal">
                Assess pre-existing condition clocks and exclusions.
              </p>
            </div>
          </div>
        </div>

        {/* Bottom Trust Sign-off */}
        <div className="relative z-10 flex items-center justify-between border-t border-slate-800/70 pt-5 text-xs text-slate-400">
          <span>&copy; {new Date().getFullYear()} CoverScope Technologies</span>
          <span>India-First Policy Intelligence</span>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* AUTHENTICATION FORM PANEL (Right 48-50%) */}
      {/* ========================================================================= */}
      <div className="flex w-full flex-col justify-center px-6 py-10 lg:w-1/2 sm:px-12 md:px-16 xl:px-24">
        {/* Mobile/Tablet Brand Header (Visible only on < lg) */}
        <div className="mx-auto w-full max-w-[420px] mb-8 lg:hidden">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white shadow-xs">
              <Shield className="h-5 w-5 stroke-[2.4]" />
            </div>
            <div>
              <span className="text-xl font-bold tracking-tight text-slate-900">
                Cover<span className="text-emerald-600">Scope</span>
              </span>
              <p className="text-xs text-slate-500 font-medium">Your policy. Made clear.</p>
            </div>
          </div>
        </div>

        {/* Auth Form Card */}
        <div className="mx-auto w-full max-w-[420px]">
          <div className="rounded-2xl border border-slate-200/80 bg-white p-7 sm:p-9 shadow-[0_4px_24px_-4px_rgba(15,23,42,0.05)]">
            {/* Form Header */}
            <div className="mb-6">
              <h2 className="text-2xl sm:text-[26px] font-bold tracking-tight text-slate-900">
                {title}
              </h2>
              <p className="text-xs sm:text-sm text-slate-500 mt-1.5 leading-relaxed">
                {subtitle}
              </p>
            </div>

            {/* Main Form Slot */}
            {children}

            {/* Alternative Action (Switch between Login / Register) */}
            <div className="mt-6 border-t border-slate-100 pt-5 text-center text-xs text-slate-600">
              {alternateAction}
            </div>
          </div>

          {/* Sub-card security badge */}
          <div className="mt-5 text-center text-[11px] text-slate-400 flex items-center justify-center gap-1.5">
            <Lock className="h-3 w-3 text-slate-400" />
            <span>Protected by salted PBKDF2 authentication &amp; encrypted sessions</span>
          </div>
        </div>
      </div>
    </div>
  );
};
