# 🛡️ CoverScope — Health Insurance Policy Intelligence Platform

<p align="center">
  <strong>Evidence-Grounded Policy Intelligence, Deterministic Rule Evaluation & Pre-Admission Claim Rehearsal</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Vite%205-61DAFB?logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-MongoDB%20Atlas%20%7C%20GridFS-47A248?logo=mongodb&logoColor=white" alt="MongoDB Atlas" />
  <img src="https://img.shields.io/badge/AI%20Inference-Groq%20Cloud%20(GPT--OSS--120B)-F55036?logo=speedtest&logoColor=white" alt="Groq AI" />
  <img src="https://img.shields.io/badge/Tests-285%20Passed%20(100%25)-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/Engine-Deterministic%20Zero--Trust-blueviolet" alt="Deterministic Engine" />
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License" />
</p>

---

## 📽️ Project Explanation & Video Walkthrough

> ### 🔗 **[Click Here to Watch Project Explanation & Demo on Google Drive](https://drive.google.com/drive/folders/1B_8_sample_drive_link_replace_with_yours?usp=sharing)** 
>
> 📌 *Replace the link above with your official Google Drive URL. This presentation covers the architectural design, zero-trust citation verifier, deterministic claim simulation, and a full live user journey from document ingestion to pre-hospitalization claim rehearsal.*

---

## 📑 Table of Contents

- [🛡️ CoverScope — Health Insurance Policy Intelligence Platform](#️-coverscope--health-insurance-policy-intelligence-platform)
  - [📽️ Project Explanation \& Video Walkthrough](#️-project-explanation--video-walkthrough)
  - [📑 Table of Contents](#-table-of-contents)
  - [1. Executive Overview \& The Problem](#1-executive-overview--the-problem)
    - [The Real-World Crisis:](#the-real-world-crisis)
  - [2. The CoverScope Zero-Trust Difference](#2-the-coverscope-zero-trust-difference)
  - [3. Workspaces \& Core Capabilities](#3-workspaces--core-capabilities)
    - [💬 Ask My Policy (Grounded Q\&A \& Intent Router)](#-ask-my-policy-grounded-qa--intent-router)
    - [🏥 Claim Rehearsal Simulator](#-claim-rehearsal-simulator)
    - [⚙️ Deterministic Scenario Analyzer](#️-deterministic-scenario-analyzer)
    - [⚖️ Cross-Policy Comparison Matrix](#️-cross-policy-comparison-matrix)
    - [🔍 Policy Explorer \& Fact Grounding](#-policy-explorer--fact-grounding)
    - [📁 Document Library \& GridFS Cloud Store](#-document-library--gridfs-cloud-store)
  - [4. System Architecture \& Data Flow](#4-system-architecture--data-flow)
  - [5. Technology Stack](#5-technology-stack)
    - [Frontend Architecture](#frontend-architecture)
    - [Backend \& AI Engines](#backend--ai-engines)
    - [Database \& Storage](#database--storage)
  - [6. API Endpoints Reference](#6-api-endpoints-reference)
  - [7. Local Setup \& Quick Start](#7-local-setup--quick-start)
    - [Prerequisites](#prerequisites)
    - [Step 1: Clone Repository \& Setup Backend](#step-1-clone-repository--setup-backend)
    - [Step 2: Configure Environment Variables](#step-2-configure-environment-variables)
    - [Step 3: Install Frontend Dependencies](#step-3-install-frontend-dependencies)
    - [Step 4: Run the Application](#step-4-run-the-application)
      - [Option A: Full-Stack Development Mode (Dual Process)](#option-a-full-stack-development-mode-dual-process)
      - [Option B: Standalone Unified Production Server](#option-b-standalone-unified-production-server)
  - [8. Production Cloud Deployment](#8-production-cloud-deployment)
    - [Backend Deployment (Render / Railway / AWS ECS)](#backend-deployment-render--railway--aws-ecs)
    - [Frontend Deployment (Vercel / Netlify)](#frontend-deployment-vercel--netlify)
  - [9. Testing, Benchmark \& Quality Verification](#9-testing-benchmark--quality-verification)
    - [What the Test Suite Verifies:](#what-the-test-suite-verifies)
  - [10. Project Directory Layout](#10-project-directory-layout)
  - [11. Legal Disclaimer](#11-legal-disclaimer)

---

## 1. Executive Overview & The Problem

Indian health insurance policies are notoriously dense legal instruments—often **30 to 60 pages** of fine print filled with complex room-rent proportionate deductions, pre-existing disease (PED) waiting periods, procedural sublimits, and mandatory co-payments.

### The Real-World Crisis:
- **70% of Claim Reductions** occur due to non-medical consumables, unverified room-category upgrades, or premature claims made during waiting periods.
- **Generic LLM Chatbots Fail**: Standard generative models hallucinate coverage approvals, fabricate policy clauses, or confuse general health tips with active contractual covenants.
- **The Financial Shock**: Policyholders only discover exclusions at the hospital billing desk when faced with unexpected **₹50,000 – ₹2,50,000** out-of-pocket bills.

**CoverScope** solves this by bridging the gap between natural language policy inquiries and contractual certainty. It combines high-speed Groq AI inference (`openai/gpt-oss-120b`) with a **deterministic Python verification kernel** that guarantees every single claim and verdict is backed by verbatim, mathematically verified policy text.

---

## 2. The CoverScope Zero-Trust Difference

| Feature | Generic AI Wrapper / Chatbot | 🛡️ CoverScope Platform |
| :--- | :--- | :--- |
| **Citation Integrity** | Hallucinates quotes or paraphrases clauses | **Verbatim Unicode substring matching** in Python; rejects ungrounded quotes |
| **Coverage Verdicts** | Confidently answers "Yes, covered!" | Strict categorical taxonomy (`Covered`, `Excluded`, `Depends`, `Not Stated`) |
| **Waiting Periods & Co-pays** | LLM guesses arithmetic and timeframes | **Headless deterministic rule engine** (zero LLM variance) |
| **Room Rent Penalties** | Often ignores proportionate deductions | Automatically calculates tariff penalties if room category exceeds policy cap |
| **Intent Handling** | Blurs specific claims with general advice | **5-Tier Intent Classifier** separating policy questions from general health guidance |
| **Data Privacy** | Stores raw files insecurely or in public buckets | **Owner-scoped MongoDB GridFS** with cascading erasure and zero plaintext disk exposure |

---

## 3. Workspaces & Core Capabilities

```text
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              COVERSCOPE WORKSPACE SUITE                                │
├──────────────────────────┬─────────────────────────────┬───────────────────────────────┤
│    💬 Ask My Policy      │     🏥 Claim Rehearsal      │     ⚙️ Scenario Analyzer      │
│  Evidence-grounded Q&A   │  Pre-admission simulations, │  Deterministic PED durations, │
│  with verbatim citations │  deductions & TPA queries   │  injury waivers & co-payments │
├──────────────────────────┼─────────────────────────────┼───────────────────────────────┤
│   ⚖️ Policy Comparison   │     🔍 Policy Explorer      │     📁 Document Library       │
│  Side-by-side dimensions │  Verbatim text viewer and   │  Secure GridFS store with     │
│  & protection gap alerts │  structured candidate facts │  owner-scoped data isolation  │
└──────────────────────────┴─────────────────────────────┴───────────────────────────────┘
```

### 💬 Ask My Policy (Grounded Q&A & Intent Router)
- **Natural Language Inquiry**: Answers complex questions regarding surgical coverage, day-care treatments, AYUSH benefits, and organ donor expenses.
- **5-Way Query Intent Classification**:
  1. *Specific Coverage Question* ("Is my knee surgery covered?")
  2. *General Policy Overview* ("What does my policy cover?")
  3. *Exclusion Summary* ("What are the permanent exclusions?")
  4. *Focused Clause Explanation* ("Explain the pre-existing disease waiting period")
  5. *General Insurance Education* ("How does health insurance portability work?")
- **Evidence Integrity & Verification Badge**: The "CoverScope Verified" badge is displayed **only** when all retrieved citations pass rigorous Unicode NFKC substring verification against the original document chunks.
- **ChatGPT / Gemini UX**: Complete with an obsidian fixed sidebar, session history persistence, collapsible past dialogues, and a floating dock input bar.

### 🏥 Claim Rehearsal Simulator
- **Pre-Hospitalization Stress Test**: Simulates planned hospital stays before pre-authorization submission.
- **Financial Liability Calculator**:
  - Predicts estimated bill vs. insurer liability vs. policyholder out-of-pocket expense.
  - Accounts for entry-age co-pays, sublimits (e.g. Cataract ₹40k cap), and proportionate room-rent deductions.
- **Interactive Action Checklist**: Grouped into *Pre-Admission*, *Medical Records*, *Financial Clearances*, and *TPA Coordination*.
- **Targeted TPA / Insurer Scripts**: Generates ready-to-copy contractual questions to ask hospital TPAs to prevent claim settlement disputes.

### ⚙️ Deterministic Scenario Analyzer
- **Zero-LLM Rule Engine**: 100% deterministic evaluation of waiting periods and policy clauses:
  - **Pre-Existing Disease (PED)**: Accurately checks elapsed policy tenure against 12, 24, 36, or 48-month waiting periods.
  - **Initial 30-Day Illness Waiting Period**: Validates elapsed policy days and respects statutory accidental injury waivers.
  - **Specific Ailment Waiting Periods**: Resolves 24-month waiting periods for cataracts, joint replacements, hernias, and kidney stones.
  - **Entry-Age Co-Payments**: Evaluates senior citizen co-payment thresholds (e.g., 61+ years) and correctly differentiates 0% base plans.

### ⚖️ Cross-Policy Comparison Matrix
- **7-Dimension Side-by-Side Analysis**: Evaluates Sum Insured, PED Waiting Periods, Initial Waiting Period, Specific Disease Waiting Periods, Co-payments, Bariatric/Obesity Surgery limits, and Modern Treatment allowances.
- **Protection Gap Indicator**: Flags disadvantageous clauses, restrictive room-rent limits, or extended waiting periods with severity alerts (`Caution`, `Conditional Gap`).

### 🔍 Policy Explorer & Fact Grounding
- **Page-by-Page Viewer**: Inspect extracted text chunks alongside character counts and page indices.
- **Candidate Fact Discovery**: Automatically extracts structured facts (waiting periods, exclusions, limits, co-payments) with extraction confidence and conditionality flags.

### 📁 Document Library & GridFS Cloud Store
- **Drag-and-Drop Ingestion**: Upload official policy wordings in PDF format (up to 20MB).
- **Owner-Scoped Tenant Isolation**: Every document, Q&A session, and simulation is strictly bound to the authenticated user ID.
- **Cascading Database Erasure**: Deleting a policy cleans up GridFS binary chunks, metadata, conversation threads, and rehearsal records.

---

## 4. System Architecture & Data Flow

```text
                                  ┌───────────────────────────────┐
                                  │      React 18 + Vite SPA      │
                                  │  Tailwind CSS • Lucide Icons  │
                                  └───────────────┬───────────────┘
                                                  │ HTTPS / REST (JWT Bearer)
                                                  ▼
                                  ┌───────────────────────────────┐
                                  │      FastAPI REST Gateway     │
                                  │   Pydantic v2 • CORS Guard    │
                                  └───────┬───────────────┬───────┘
                                          │               │
                     ┌────────────────────┘               └────────────────────┐
                     ▼                                                         ▼
       ┌───────────────────────────┐                             ┌───────────────────────────┐
       │   Ingestion & Retrieval   │                             │   Deterministic Engines   │
       │  • PyMuPDF Text Extractor │                             │  • Waiting Period Engine  │
       │  • Unicode NFKC Matcher   │                             │  • Room Rent Calculator   │
       │  • Smart Intent Router    │                             │  • Co-Pay Tariff Engine   │
       │  • Lexical BM25 Ranker    │                             │  • Claim Rehearsal Core   │
       └─────────────┬─────────────┘                             └─────────────┬─────────────┘
                     │ Retrieved Chunks                                        │
                     ▼                                                         │
       ┌───────────────────────────┐                                           │
       │     Groq Cloud LLM        │                                           │
       │   openai/gpt-oss-120b     │                                           │
       │   Structured JSON Schema  │                                           │
       └─────────────┬─────────────┘                                           │
                     │ Draft Response & Citations                              │
                     ▼                                                         │
       ┌───────────────────────────┐                                           │
       │  Python Citation Verifier │                                           │
       │  Verbatim Quote Match?    │                                           │
       │  Chunk & Page Grounded?   │                                           │
       └─────────────┬─────────────┘                                           │
                     │ Verified Payload                                        │
                     └────────────────────┬────────────────────────────────────┘
                                          ▼
                               ┌───────────────────────────┐
                               │    Persistence Layer      │
                               │   MongoDB Atlas / GridFS  │
                               │  • User Profiles (PBKDF2) │
                               │  • GridFS PDF Documents   │
                               │  • Dialogue History Store │
                               │  • Simulation Audits      │
                               └───────────────────────────┘
```

---

## 5. Technology Stack

### Frontend Architecture
- **Framework**: React 18 + TypeScript
- **Build Tool**: Vite 5 (Fast HMR, optimized production chunks)
- **Styling**: Tailwind CSS with custom medical InsurTech palette (`emerald`, `slate`, `amber`, `rose`)
- **Routing**: React Router DOM v6
- **Animations & Icons**: Lucide React + GSAP
- **State Management**: Native React Context (`AuthContext`) + type-safe REST client

### Backend & AI Engines
- **API Framework**: FastAPI 0.115+ (Python 3.11+)
- **ASGI Server**: Uvicorn
- **PDF Engine**: PyMuPDF (`fitz` / `pymupdf < 2.0`)
- **Data Validation**: Pydantic v2
- **AI Model**: `openai/gpt-oss-120b` via Groq Cloud High-Speed Inference
- **Deterministic Evaluation**: Pure Python rule engines for claims, waiting periods, and tariffs

### Database & Storage
- **Database**: MongoDB Atlas (GridFS for binary PDF chunks + native collections for metadata)
- **Authentication**: JWT Bearer tokens with SHA-256 PBKDF2 password hashing
- **Local Fallback**: Automatically falls back to local data store (`data/local_users.json`) if MongoDB URI is omitted, allowing complete offline functionality

---

## 6. API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `POST` | `/api/v1/auth/register` | Register new user account (salted PBKDF2) | No |
| `POST` | `/api/v1/auth/login` | Authenticate user & issue JWT Bearer Token | No |
| `GET` | `/api/v1/auth/me` | Retrieve profile of the current authenticated user | Yes |
| `GET` | `/api/v1/policies` | List all uploaded policies for the authenticated user | Yes |
| `POST` | `/api/v1/policies/upload` | Upload policy PDF (ingested into MongoDB GridFS) | Yes |
| `GET` | `/api/v1/policies/{id}` | Retrieve policy details, metadata, and extracted facts | Yes |
| `DELETE` | `/api/v1/policies/{id}` | Cascading deletion of policy, chunks, and chat history | Yes |
| `POST` | `/api/v1/qa/ask` | Ask coverage question (Intent routing + Verbatim quotes) | Yes |
| `GET` | `/api/v1/qa/conversations` | Retrieve past Q&A conversations list | Yes |
| `GET` | `/api/v1/qa/conversations/{id}` | Fetch full message thread for a policy conversation | Yes |
| `POST` | `/api/v1/scenarios/evaluate` | Deterministic evaluation of waiting periods & co-pay | Yes |
| `POST` | `/api/v1/rehearsal/simulate` | Run pre-hospitalization claim rehearsal simulation | Yes |
| `GET` | `/api/v1/rehearsal/history` | Retrieve past claim rehearsal records | Yes |
| `POST` | `/api/v1/comparison/matrix` | Compare two policies across 7 standardized dimensions | Yes |
| `GET` | `/api/v1/dashboard/metrics` | Retrieve aggregated portfolio & policy analytics | Yes |
| `GET` | `/api/v1/health` | System health check (Database, Storage, & AI status) | No |

---

## 7. Local Setup & Quick Start

### Prerequisites
- **Python**: 3.11 or higher
- **Node.js**: 18.0 or higher (with `npm`)
- **Groq API Key**: Free API key from [console.groq.com](https://console.groq.com)
- **MongoDB Atlas** (Optional): Free M0 cluster URI (runs locally if omitted)

---

### Step 1: Clone Repository & Setup Backend

```powershell
# 1. Clone repository
git clone https://github.com/<your-username>/coverscope.git
cd coverscope

# 2. Create and activate Python virtual environment
python -m venv .venv
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On macOS / Linux:
# source .venv/bin/activate

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 2: Configure Environment Variables

Create a `.env` file in the repository root (or copy from `.env.example`):

```dotenv
# AI LLM Provider (Required for natural language Q&A)
GROQ_API_KEY=gsk_your_groq_api_key_here
COVERSCOPE_GROQ_MODEL=openai/gpt-oss-120b

# Database Persistence (Optional: falls back to local data store if omitted)
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=CoverScope
MONGODB_DATABASE=coverscope

# Security & JWT Token Signing
COVERSCOPE_JWT_SECRET=super_secret_production_key_replace_with_32_random_bytes
```

---

### Step 3: Install Frontend Dependencies

```powershell
npm install --prefix frontend
```

---

### Step 4: Run the Application

#### Option A: Full-Stack Development Mode (Dual Process)

In **Terminal 1** (Start FastAPI Backend):
```powershell
python -m backend.main
```
*Backend runs on `http://localhost:8000` (Interactive Swagger docs: `http://localhost:8000/docs`).*

In **Terminal 2** (Start React Frontend with Vite HMR):
```powershell
npm run dev --prefix frontend
```
*Frontend will launch at `http://localhost:5173`.*

#### Option B: Standalone Unified Production Server
Because the React single page app compiles directly into `frontend/dist/`, running `python -m backend.main` serves the complete React SPA, API routes, and static assets from `http://localhost:8000/` in a single command!

---

## 8. Production Cloud Deployment

CoverScope is engineered for decoupled cloud deployment:

### Backend Deployment (Render / Railway / AWS ECS)
1. **Docker Runtime**: The repository includes a production-ready `Dockerfile`. Render auto-detects it.
2. Set Environment Variables: `GROQ_API_KEY`, `MONGODB_URI`, `COVERSCOPE_JWT_SECRET`, and `PYTHONPATH=.`.
3. Set Health Check path to `/api/v1/health`.

### Frontend Deployment (Vercel / Netlify)
1. Link your Git repository to **Vercel**.
2. Set **Root Directory** to `frontend`.
3. Set **Framework Preset** to `Vite`.
4. Configure Environment Variable:
   - `VITE_API_BASE_URL`: `https://<your-backend-api-domain>.com`
5. The included [`frontend/vercel.json`](file:///d:/MERN_ENDTERM_PROJECT/frontend/vercel.json) handles SPA client-side routing automatically.

---

## 9. Testing, Benchmark & Quality Verification

CoverScope includes a 100% offline-evaluable automated test suite:

```powershell
# Run the complete test suite
pytest -q
```

```text
........................................................................ [ 25%]
........................................................................ [ 50%]
........................................................s............... [ 75%]
......................................................................   [100%]
===================== 285 passed, 1 skipped in 18.38s =====================
```

### What the Test Suite Verifies:
1. **Evidence Grounding**: Mathematical verification of Unicode NFKC normalization and quote boundaries.
2. **Deterministic Waiting Periods**: Pre-existing disease duration conversions (years to months) and 30-day initial illness waivers.
3. **Claim Rehearsal Accuracy**: Correct computation of room-rent proportionate deductions, procedural sublimits, and out-of-pocket liabilities.
4. **Tenant Isolation**: Multi-tenant database boundary verification (users cannot query or delete unowned records).
5. **Contract Compatibility**: Dual-ID resolution (MongoDB `_id` vs SHA-256 fingerprint) and cascading resource destruction.

---

## 10. Project Directory Layout

```text
coverscope/
├── backend/                       # Python FastAPI Application Core
│   ├── api/                       # REST endpoints (auth, policies, qa, scenarios, rehearsal, etc.)
│   ├── database/                  # MongoDB Atlas client, repositories, GridFS storage, indexes
│   ├── document_processing/       # PyMuPDF text extraction, Unicode NFKC normalizer, chunker
│   ├── domain/                    # Deterministic rule engines, scenario & comparison models
│   ├── llm/                       # Resilient Groq Cloud SDK client & error handlers
│   ├── qa/                        # Intent classifier, BM25 retrieval ranker, citation verifier
│   ├── services/                  # Headless business services (PolicyService, AuthService, etc.)
│   ├── config.py                  # Pydantic application settings & environment schema
│   └── main.py                    # Server entrypoint, CORS configuration & lifespan events
├── frontend/                      # React 18 + TypeScript + Vite Single Page Application
│   ├── src/
│   │   ├── components/            # Reusable components (Navbar, Footer, CardTilt, Badges)
│   │   ├── context/               # AuthContext (JWT session state, token persistence)
│   │   ├── layouts/               # AppLayout (ChatGPT-style dual pane & standard layouts)
│   │   ├── lib/                   # Typed API client, TypeScript definitions, helpers
│   │   └── pages/                 # AskPolicy, ClaimRehearsal, Explorer, Comparison, Dashboard
│   ├── package.json               # Frontend dependencies & npm scripts
│   ├── tailwind.config.js         # Healthcare InsurTech color palette & design tokens
│   └── vite.config.ts             # Vite bundler configuration & backend API reverse proxy
├── evaluation/                    # Ground-truth benchmarks & gold fact datasets
│   ├── comparison_benchmarks.json # Standardized comparison evaluation dimensions
│   ├── gold_facts.json            # Verified policy facts for offline evaluation tests
│   ├── questions.json             # Benchmark QA evaluation suite
│   └── schedule_benchmarks.json   # Waiting period & sublimit evaluation benchmarks
├── pdfs/                          # Public benchmark insurance policy schedules
├── scripts/                       # Operational CLI utilities, DB healthcheck, and smoke tests
├── tests/                         # Comprehensive 285-test automated test suite
├── .env.example                   # Environment variable template
├── Dockerfile                     # Multi-stage production container definition
├── package.json                   # Root monorepo workspace orchestration
├── pytest.ini                     # Pytest configuration
├── requirements.txt               # Pinned Python backend dependencies
└── README.md                      # Platform documentation
```

---

## 11. Legal Disclaimer

> [!IMPORTANT]
> **CoverScope is an automated informational intelligence and pre-admission simulation tool** designed to assist policyholders in understanding dense policy wording and contractual provisions. It does **not** constitute legal advice, insurance underwriting, or a formal claim settlement guarantee. All final claim settlements, pre-authorizations, and coverage decisions are governed strictly by the respective insurance company and the terms stated in your active Policy Schedule and IRDAI regulations.

---

<p align="center">
  Built with ❤️ for Indian policyholders • Engineered for clinical evidence integrity and zero-trust certainty.
</p>
