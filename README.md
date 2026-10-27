# CoverScope

<p align="center">
  <strong>Evidence-Grounded Health Insurance Policy Intelligence & Claim Rehearsal Platform</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Frontend-React%2018%20%7C%20TypeScript%20%7C%20Vite-61DAFB?logo=react&logoColor=black" alt="React 18" />
  <img src="https://img.shields.io/badge/Backend-FastAPI%20%7C%20Python%203.11+-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Database-MongoDB%20Atlas%20%7C%20GridFS-47A248?logo=mongodb&logoColor=white" alt="MongoDB Atlas" />
  <img src="https://img.shields.io/badge/AI%20Inference-Groq%20Cloud%20(GPT--OSS--120B)-F55036?logo=speedtest&logoColor=white" alt="Groq AI" />
  <img src="https://img.shields.io/badge/Tests-229%20Passed%20(100%25)-brightgreen" alt="Tests" />
  <img src="https://img.shields.io/badge/License-MIT-blue" alt="License" />
</p>

---

## 1. Executive Overview

**CoverScope** is a full-stack, clinical-grade health insurance intelligence platform engineered to eliminate ambiguity, fine-print surprises, and claim rejections for Indian individual health insurance policies.

Unlike generic chatbot wrappers that hallucinate coverage terms, CoverScope operates on a **zero-trust, evidence-grounded architecture**:
1. **Verbatim Grounding in Python**: The LLM never decides coverage unverified. Every citation quote is mathematically matched against raw extracted PDF text using Unicode-normalized substring verification in Python before any verdict is surfaced.
2. **Deterministic Domain Engines**: Waiting periods, conditional exclusions, room rent caps, procedure sub-limits, and entry-age co-payments are evaluated by headless deterministic rule engines with zero LLM variance.
3. **Pre-Hospitalization Claim Rehearsal**: Simulates planned hospital admissions to forecast out-of-pocket financial exposure, mandatory checklists, and precise TPA queries before stepping into the hospital.
4. **Cloud-Native MongoDB GridFS Storage**: User-uploaded documents are securely stored in MongoDB Atlas GridFS with strict owner-scoped isolation, cascading deletion, and zero plaintext exposure on local disk.

---

## 2. Core Workspaces & Capabilities

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                            COVERSCOPE WORKSPACES                            │
├─────────────────────┬──────────────────────┬────────────────────────────────┤
│   Ask My Policy     │   Claim Rehearsal    │      Scenario Analyzer         │
│ Evidence-backed Q&A │ Financial exposure   │ Deterministic waiting periods  │
│ with Python quotes  │ & TPA checklist      │ & co-payment evaluation        │
├─────────────────────┼──────────────────────┼────────────────────────────────┤
│  Policy Comparison  │   Policy Explorer    │      Document Library          │
│ Side-by-side matrix │ Verbatim text viewer │ GridFS multi-policy store with │
│  & protection gaps  │ & extracted facts    │ cascading database erasure     │
└─────────────────────┴──────────────────────┴────────────────────────────────┘
```

### 1. Ask My Policy (Evidence-Grounded Q&A)
- Natural language coverage inquiries answered strictly from retrieved policy evidence.
- **Categorical Verdicts**: `Covered`, `Excluded`, `Depends`, or `Not Stated`.
- **Python-Side Citation Verifier**: Enforces chunk verification, minimum substantive character lengths, ellipsis boundary checks, and multi-column token tolerances.
- **Safe Fallback**: If a quotation does not match source text, the UI automatically downgrades the answer to `Depends` with a prominent **Manual Review Required** badge and displays the unverified text in a safety quarantine.
- **Persistent Chat History**: Rehydrates previous policy dialogues directly from MongoDB Atlas across browser refreshes and login sessions.

### 2. Claim Rehearsal Simulator
- Pre-admission hospitalization simulator tailored for the Indian healthcare and TPA landscape.
- **Financial Exposure Calculator**: Computes estimated out-of-pocket liabilities, age-based co-payments, procedure-specific sublimits (e.g. Cataract ₹40,000 sub-limit), room category proportionate deduction penalties, and non-medical consumables.
- **TPA Pre-Admission Checklist**: Actionable steps categorized into Pre-Admission, Documentation, Financial, and TPA Coordination.
- **Targeted Questions for Insurer / TPA**: Exact contractual questions to clarify cashless approvals prior to admission.

### 3. Scenario Analyzer (Deterministic Rule Engine)
- Headless, rule-based scenario evaluation with **zero LLM dependencies**:
  - **Pre-Existing Disease (PED)**: Calculates elapsed duration against 12, 24, 36, or 48-month waiting periods (properly converting years to months).
  - **Initial 30-Day Illness Waiting Period**: Validates elapsed policy days and respects accidental injury waivers.
  - **Specific Ailment Waiting Periods**: Resolves 24-month waiting periods for cataracts, joint replacements, hernias, and kidney stones.
  - **Entry-Age Co-Payments**: Dynamically extracts policy age thresholds (e.g. 61+ years) and accurately differentiates 0% base policies from age-exempt policies.

### 4. Cross-Policy Comparison Engine
- Compares two insurance policies across 7 standardized dimensions: Sum Insured, PED Waiting Period, Initial Waiting Period, Specific Disease Waiting Period, Co-payment, Obesity Exclusion, and Alcoholism/Substance Abuse Exclusion.
- **Protection Gap Analysis**: Identifies restrictive terms, longer waiting periods, or missing covers with actionable severity indicators (`Caution`, `Conditional Gap`).
- Direct verbatim evidence links for both compared policies.

### 5. Policy Explorer & Fact Grounding
- Page-by-page reader showing verbatim extracted policy text and page character statistics.
- **Extracted Policy Facts**: Discovers candidate facts (waiting periods, exclusions, limits, co-payments) with page citations, extraction confidence, and conditionality triggers.

### 6. Document Library & Cloud Storage
- Drag-and-drop ingestion of official policy wordings (PDF, max 20MB).
- Multi-policy registry backed by MongoDB Atlas GridFS.
- **1 Baseline Demonstration Policy**: Ships with 1 official pre-cached demo policy (*Star Comprehensive Insurance Policy*) while allowing unlimited user uploads.
- **Cascading Database Erasure**: Deleting a policy purges GridFS binary chunks, metadata, linked Q&A conversations, messages, and analysis records across both MongoDB `_id` and SHA-256 fingerprint references.

---

## 3. System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REACT 18 SINGLE PAGE APP                           │
│                   Vite • TypeScript • Tailwind CSS • Lucide                 │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ REST API (Bearer JWT / JSON)
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FASTAPI REST API GATEWAY                            │
│                 Uvicorn • Pydantic v2 • Starlette Middleware                │
├─────────────────────────────────────────────────────────────────────────────┤
│  /api/v1/auth        - User registration, login (PBKDF2), profile, JWT      │
│  /api/v1/policies    - Upload (GridFS), detail, pages, facts, delete        │
│  /api/v1/qa          - Grounded Q&A, Python citation audit, chat history    │
│  /api/v1/scenarios   - Deterministic waiting period & copay evaluation      │
│  /api/v1/rehearsal   - Claim rehearsal simulation & out-of-pocket breakdown │
│  /api/v1/comparison  - Side-by-side dimension matrix & protection gaps      │
│  /api/v1/dashboard   - Aggregated metrics & active document inventory       │
└──────────────┬───────────────────────┬───────────────────────────────┬──────┘
               │                       │                               │
               ▼                       ▼                               ▼
    ┌──────────────────────┐ ┌──────────────────┐  ┌────────────────────────┐
    │   DOCUMENT PIPELINE  │ │  INFERENCE & QA  │  │   PERSISTENCE LAYER    │
    │  PyMuPDF (fitz)      │ │  Deterministic   │  │   MongoDB Atlas Cloud  │
    │  Unicode Normalizer  │ │   Lexical Search │  │  • GridFS (Raw PDFs)   │
    │  Quality Guards      │ │  Groq LLM Client │  │  • Users (Salted Hash) │
    │  Page Chunker        │ │   (GPT-OSS-120B) │  │  • Policies & Metadata │
    │  Adapter Heuristics  │ │  Python Citation │  │  • Dialogue History    │
    │                      │ │   Verifier       │  │  • Analysis Audits     │
    └──────────────────────┘ └──────────────────┘  └────────────────────────┘
```

---

## 4. Technology Stack

### Frontend
- **Framework**: React 18 with TypeScript
- **Bundler & Dev Server**: Vite 5
- **Styling**: Tailwind CSS with custom healthcare InsurTech design tokens
- **Routing**: React Router DOM v6
- **Icons**: Lucide React
- **State & Networking**: Native Context API (`AuthContext`) + typed Fetch Client

### Backend & Core Engines
- **API Framework**: FastAPI 0.115+ (Python 3.11+)
- **ASGI Web Server**: Uvicorn
- **PDF Processing**: PyMuPDF (`fitz` / `pymupdf`)
- **Data Validation**: Pydantic v2
- **Lexical Retrieval**: Custom token-frequency & phrase-cooccurrence ranking (no vector DB required)
- **AI Inference**: Groq Cloud SDK (`openai/gpt-oss-120b`) with strict JSON schema enforcement

### Database & Security
- **Cloud Database**: MongoDB Atlas (compatible with M0 Free Tier through dedicated clusters)
- **Document Store**: MongoDB GridFS for raw PDF chunks with zero plaintext exposure on local disk
- **Authentication**: JWT Bearer Tokens with SHA-256 PBKDF2 password hashing and user-scoped query isolation
- **CORS Protection**: Starlette CORSMiddleware supporting local development and production domains

---

## 5. Security, Privacy & Integrity Guarantees

1. **Zero Raw PDF Disk Exposure**:
   - Uploaded PDF bytes are ingested in memory, stored directly into MongoDB Atlas GridFS, and never written to disk as temporary files.
2. **Owner-Scoped Multi-Tenant Isolation**:
   - Every database query strictly filters by the authenticated `user_id`. Users cannot view, query, or delete documents or chat records belonging to other users.
3. **Python Citation Safeguards**:
   - Chunk IDs must exist in retrieved evidence.
   - Quotations must match source text after Unicode NFKC and whitespace normalization.
   - Minimum quote length (`MIN_QUOTE_MATCH_CHARS = 12`) prevents punctuation matching.
   - Page numbers always come from trusted chunk metadata, never the LLM.
4. **Credential Redaction**:
   - Database connection URIs, passwords, and Groq API keys are automatically redacted in health checks, application logs, and API error responses.

---

## 6. Local Quick Start

### Prerequisites
- **Python**: Version 3.11 or higher
- **Node.js**: Version 18 or higher (with `npm`)
- **MongoDB Atlas**: Free Tier cluster URI (optional — runs in in-memory session mode if omitted)
- **Groq API Key**: Free API key from [console.groq.com](https://console.groq.com)

### 1. Clone & Set Up Python Environment

```powershell
# Clone the repository
git clone https://github.com/<your-username>/coverscope.git
cd coverscope

# Create and activate Python virtual environment
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Set Up Frontend Dependencies

```powershell
npm install --prefix frontend
```

### 3. Configure Environment Variables

Create a `.env` file in the repository root (copied from `.env.example`):

```dotenv
# AI LLM Provider (Required for Ask My Policy)
GROQ_API_KEY=gsk_your_groq_api_key_here
COVERSCOPE_GROQ_MODEL=openai/gpt-oss-120b

# MongoDB Atlas Persistence (Optional: falls back to in-memory mode if unset)
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=CoverScope
MONGODB_DATABASE=coverscope

# Security & JWT Configuration
COVERSCOPE_JWT_SECRET=super_secret_production_key_replace_with_32_random_bytes
```

### 4. Run CoverScope

#### Option A: Run Full Stack (Development Mode)

In **Terminal 1** (Start FastAPI Backend):
```powershell
python -m backend.main
```
*Backend API will run at `http://localhost:8000` (Interactive Swagger docs at `http://localhost:8000/docs`).*

In **Terminal 2** (Start React Frontend with Vite HMR):
```powershell
npm run dev --prefix frontend
```
*Frontend will be live at `http://localhost:5173`.*

#### Option B: Standalone Unified Production Server
Because the React app is pre-compiled under `frontend/dist/`, running `python -m backend.main` alone serves the complete React SPA directly at `http://localhost:8000/`!

---

## 7. Production Deployment (Vercel + Render)

CoverScope is pre-configured for a modern decoupled cloud deployment:

### Backend Deployment (Render)
1. Link your repository to [Render](https://render.com) and create a **Web Service**.
2. **Environment**: `Python 3`
3. **Build Command**:
   ```bash
   pip install --upgrade pip && pip install -r requirements.txt
   ```
4. **Start Command**:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port $PORT
   ```
5. **Environment Variables**: Add `MONGODB_URI`, `GROQ_API_KEY`, `COVERSCOPE_JWT_SECRET`, `COVERSCOPE_GROQ_MODEL`, and `PYTHONPATH=.`.

### Frontend Deployment (Vercel)
1. Import the repository into [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Set **Framework Preset** to `Vite`.
4. Add Environment Variable:
   - `VITE_API_BASE_URL`: `https://<your-render-backend-name>.onrender.com`
5. The included [`frontend/vercel.json`](file:///d:/MERN_ENDTERM_PROJECT/frontend/vercel.json) automatically handles SPA client-side routing (`/*` -> `/index.html`).

---

## 8. Test Suite & Verification

CoverScope maintains a 100% offline-evaluable automated test suite covering all layers:

```powershell
# Run the complete test suite
pytest -q
```

### Test Coverage Highlights:
- **Unit & Normalization Tests**: NFKC ligatures, character limits, quotation substring validation.
- **Domain Engine Tests**: Pre-existing disease duration conversions (years to months), initial waiting period accidental injury waivers, co-payment threshold matching.
- **Contract & API Isolation Tests**: Dual policy ID resolution (MongoDB `_id` vs fingerprint), owner-scoped upload isolation, cascading conversation/analysis deletion, and citation tolerance.
- **Current Status**: **229 passed, 1 skipped, 0 failed**.

---

## 9. Repository Layout

```text
coverscope/
├── backend/
│   ├── api/                   # FastAPI routes (auth, policies, qa, scenarios, rehearsal, etc.)
│   ├── database/              # MongoDB client, repositories, GridFS file storage, indexes
│   ├── document_processing/   # PyMuPDF extraction, normalization, chunking, quality checks
│   ├── domain/                # Canonical domain models, deterministic scenario & comparison engines
│   ├── llm/                   # Resilient Groq client with JSON code-block parsing & error mapping
│   ├── qa/                    # Lexical retrieval ranking, citation verifier, and workflow helpers
│   ├── services/              # Headless PolicyService, AuthService, and ClaimRehearsalService
│   ├── config.py              # Central Pydantic settings & environment configuration
│   └── main.py                # FastAPI application entry point, lifespan, & CORS setup
├── frontend/
│   ├── src/
│   │   ├── components/        # Navbar, badge renderers, and reusable UI elements
│   │   ├── context/           # AuthContext (login state, user profile, token persistence)
│   │   ├── layouts/           # AppLayout with responsive header & navigation
│   │   ├── lib/               # Typed API client, error handling, and TypeScript interfaces
│   │   └── pages/             # Dashboard, Ask, Explorer, Scenarios, Rehearsal, Comparison, Library
│   ├── index.html             # HTML entry point
│   ├── package.json           # Frontend dependencies & build scripts
│   ├── tailwind.config.js     # InsurTech color palette & design tokens
│   └── vite.config.ts         # Vite bundler configuration & local API proxy
├── pdfs/                      # Bundled public baseline demonstration policy
├── scripts/                   # Database migration, health checks, CLI utilities
├── tests/                     # 229 automated offline pytest test cases
├── .env.example               # Template for environment variables
├── requirements.txt           # Python dependencies
└── README.md                  # System documentation
```

---

## 10. Disclaimer

*CoverScope is an automated informational intelligence tool designed to assist policyholders in understanding insurance policy wordings. It does not constitute legal advice, insurance underwriting, or a formal claim settlement guarantee. All claim adjudications are governed strictly by the respective insurance company and the terms of your active Policy Schedule.*
