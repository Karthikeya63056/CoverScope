# CoverScope

**Your policy. Made clear.**

CoverScope is an evidence-grounded question-answering app for Indian individual
health insurance policy wordings. Upload a text-based PDF, ask a coverage
question, and get a verdict backed by a verified quotation and page reference
from that policy.

CoverScope is an informational tool. It is not insurance advice, a claim
decision, or a legal opinion.

---

## What it does

- Accepts a text-based policy PDF (no OCR).
- Extracts and quality-checks the wording, then splits it into page-scoped
  chunks such as `P12-C2`.
- Retrieves the most relevant clauses for a question using deterministic
  lexical ranking — no embeddings or vector database.
- Calls Groq (`openai/gpt-oss-120b` by default) with a strict JSON schema.

- Validates every citation in Python before showing a verdict:
  - the chunk ID must exist in the retrieved evidence;
  - the quotation must appear in that chunk after Unicode-aware normalization;
  - the page number comes from trusted chunk metadata, never the model.
- Returns a safe manual-review outcome when citations cannot be verified or a
  page is explicitly flagged as unreliable.

### Verdicts

| Verdict | Meaning |
|---|---|
| **Covered** | The wording affirmatively covers the benefit, subject to stated conditions. |
| **Excluded** | The wording affirmatively excludes the benefit or says it is not payable. |
| **Depends** | Coverage turns on a condition the evidence or question does not resolve, such as a plan, rider, or policy start date. |
| **Not stated** | The relevant provision was not found in the retrieved evidence. This does **not** mean the benefit is excluded. |

A valid quotation confirms the wording, not the coverage decision. Model-reported
confidence is shown separately from Python-side citation validity.

---

## Sample documents

Three public policy wordings are bundled under `pdfs/` for demonstrations:

- `pdfs/ReAssure 2.0 - Policy Wording.pdf`
- `pdfs/optima-secure-revision-pw.pdf`
- `pdfs/Brochure_Star_Comprehensive_Insurance_Policy_V_15_Web_633bcfcaaf.pdf`

Useful demo questions:

- Is a pre-existing disease covered in month 20?
- What waiting period applies to specified diseases?
- What exclusions apply to this policy?
- Are room-rent limits dependent on the selected plan?

These documents are public insurer wordings. Confirm redistribution terms before
publishing a fork.

---

## Architecture

```text
PDF bytes
  -> backend.document_processing.pdf_loader      validate / open in memory
  -> backend.document_processing.text_extractor  page text + diagnostics
  -> backend.document_processing.quality_checks  reject scanned/oversized docs
  -> backend.document_processing.chunker         page-scoped chunks (P12-C2)
  -> backend.qa.retrieval                        deterministic lexical ranking
  -> backend.llm.groq_client                     strict JSON schema via Groq
  -> backend.qa.answer                           citation verification + safe outcomes
  -> frontend/app.py (Streamlit) or scripts/ask_policy.py (CLI)
```

| Area | Purpose |
|---|---|
| `backend/document_processing/` | PDF loading, extraction, normalization, chunking, quality checks |
| `backend/qa/retrieval.py` | TF-IDF-style lexical ranking with phrase and coverage bonuses |
| `backend/qa/schemas.py` | Pydantic models and the strict provider JSON schema |
| `backend/qa/answer.py` | Prompt, citation validation, manual-review safeguards |
| `backend/qa/workflow.py` | Streamlit-agnostic prepare/ask helpers shared by the UI |
| `backend/llm/` | Provider-isolated Groq client, retries, application exceptions |
| `frontend/` | Streamlit app and safe UI copy |
| `scripts/` | CLI and evaluation runner |
| `evaluation/` | 17 manually checked questions across three policies |
| `tests/` | Network-independent unit and Streamlit workflow tests |

---

## Quick start

Python 3.11+ is recommended.

```powershell
cd D:\MERN_ENDTERM_PROJECT

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create a local `.env` from `.env.example` and add your Groq key:

```powershell
Copy-Item .env.example .env
notepad .env
```

```dotenv
GROQ_API_KEY=your_key_here
```

Never commit `.env`. It is already listed in `.gitignore`.

### Run the Streamlit app

```powershell
streamlit run frontend/app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

### Run the CLI

```powershell
python scripts/ask_policy.py "pdfs\ReAssure 2.0 - Policy Wording.pdf" "Is a pre-existing disease covered in month 20?"
```

### Run the tests

```powershell
pytest -q
```

The suite does not require a network connection or a live API key.

---

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | — | Required for live answers. Read from the environment or `.env`; never logged. |
| `COVERSCOPE_GROQ_MODEL` | `openai/gpt-oss-120b` | Groq model ID. |

| `COVERSCOPE_GROQ_TIMEOUT_SECONDS` | `30` | Per-request timeout. |
| `COVERSCOPE_GROQ_MAX_COMPLETION_TOKENS` | `1200` | Conservative completion budget. |
| `COVERSCOPE_MAX_EXTRACTED_CHARS` | `250000` | Reject larger documents; never truncate. |
| `COVERSCOPE_MAX_UPLOAD_BYTES` | `20000000` | Early upload-size guard (20 MB). |
| `COVERSCOPE_CHUNK_CHARS` | `1800` | Maximum characters per page-scoped chunk. |
| `COVERSCOPE_MIN_PAGE_CHARS` | `40` | Low-text page threshold for diagnostics. |
| `COVERSCOPE_RETRIEVAL_TOP_K` | `5` | Number of evidence chunks sent to the model. |
| `COVERSCOPE_UNRELIABLE_PAGES` | empty | Explicit page numbers/ranges (for example `50,51-52`) that force manual review when cited. |

Only the retrieved evidence chunks are sent to Groq — not the entire PDF.

---

## How answer validation works

1. The question is normalized and ranked against page-scoped chunks.
2. If no meaningful evidence is found, CoverScope returns **Not stated** without
   calling the model.
3. The model must return strict JSON: `verdict`, `answer`, `citations`,
   `confidence`, and `caveats`.
4. Python verifies every cited chunk ID and quotation. Page numbers are derived
   from chunk metadata.
5. If verification fails, CoverScope returns **Depends** (unless already **Not
   stated**), confidence **Low**, and a prominent manual-review warning. The
   model's original answer is preserved only as clearly labelled unverified text.
6. If a citation lands on an explicitly flagged unreliable page, definitive
   verdicts are downgraded and manual review is required.
7. The heuristic table-review flag adds a caveat only. It is not treated as proof
   that a page is wrong.

---

## Streamlit behaviour

- The selected PDF and the last result are stored in `st.session_state`.
- A SHA-256 fingerprint prevents reprocessing on every UI rerun.
- The model is called only when the user clicks **Ask CoverScope** or an explicit
  suggested-question button. Typing or changing unrelated controls does not
  trigger a request.
- Missing keys, authentication failures, timeouts, rate limits, and malformed
  provider responses become friendly messages with no raw traceback or secret.
- A rate-limit response starts a 60-second cooldown; the app does not retry
  automatically.
- A failed request preserves the last verified result and labels it as previous.
- Uploaded bytes are processed in memory. CoverScope does not write policy text
  to disk.

---

## Evaluation

`evaluation/questions.json` contains 17 manually checked questions across three
policies, covering waiting periods, exclusions, conditional benefits, and a
flagged table page.

Validate the file without a key:

```powershell
python scripts/evaluate.py --dry-run
```

Run live questions (respect the provider's token-per-minute limit):

```powershell
python scripts/evaluate.py --delay 40 --output evaluation/results.json
```

The runner reports verdict accuracy, expected-page match, citation validity,
unsupported-answer rate, and manual-review safety. Do not treat a small live
subset as a general accuracy claim.

The development key used during Phase 2 had an observed limit of roughly
**8,000 tokens per minute** and **1,000 requests per day**. Retrieval is therefore
mandatory; whole-document prompting is not viable.

---

## Supported documents and limitations

**Supported**

- Text-based, selectable-text PDFs.
- English-language individual health insurance policy wordings.
- Documents within the upload and extracted-character limits.

**Not supported**

- Scanned or image-only PDFs (OCR is not implemented).
- Password-protected PDFs.
- Non-PDF files.
- Exact reconstruction of dense multi-column benefit schedules.
- Legal advice or claim adjudication.

**Known limitations**

- Lexical retrieval can miss paraphrases that share no vocabulary with the policy.
- Chunk boundaries can split adjacent clauses; the model must quote the exact
  chunk it cites.
- Dense tables may lose row/column relationships. Explicit unreliable-page flags
  and manual-review warnings are the safeguard; table reconstruction is out of
  scope.
- Plan, sum-insured, and optional-endorsement variability correctly produces
  **Depends**, which can look like over-abstention.
- Model output is non-deterministic across runs.
- Page numbers are 1-based PDF page indices, not printed page labels.
- One document is active per browser session; there is no authentication,
  payments, or multi-user storage.

---

## Privacy and security

- `GROQ_API_KEY` is read from the environment or `.env`; it is never printed,
  logged, or committed.
- `.env` is gitignored. `.env.example` contains placeholders only.
- The PDF is processed in memory. No policy text is written to disk by the app.
- Only retrieved evidence and the question are sent to the configured LLM
  provider for analysis.
- Provider exceptions are translated to safe UI messages; raw stack traces and
  document text are not shown or logged.
- There is no authentication. Treat a public deployment as a demo and do not
  upload confidential policies.
- If a key is ever exposed in chat, logs, or a commit, rotate it immediately in
  the Groq console and update the environment secret.

---

## Deployment

CoverScope is compatible with Streamlit Community Cloud or any host that can run
a Streamlit app.

1. Push the repository to GitHub **without** `.env` or private policy PDFs.
2. Create a Streamlit app with entry point `frontend/app.py`.
3. Add `GROQ_API_KEY` through the platform's secrets manager, not a committed
   file. For Streamlit Community Cloud, use the app's **Secrets** settings:
   ```toml
   GROQ_API_KEY = "your_key_here"
   ```
4. Reboot the app so the secret is loaded.
5. Verify: upload a bundled public policy, ask a question, confirm the citation
   page and quotation, and confirm a manual-review case still refuses to show a
   definitive verdict.
6. Never deploy `.env`, and never bake a key into source or build arguments.

**Deployment status: not deployed.** Local implementation and tests are complete;
the steps above have not been executed against a live host in this repository.

---

## Test coverage

```powershell
pytest -q
```

The suite covers normalization and ligatures, the 250,000-character limit,
retrieval ranking, empty evidence, all four verdicts, unknown chunk IDs,
fabricated quotations, safe manual-review outcomes, explicit unreliable pages,
Groq error mapping and retries, CLI validation, the shared workflow layer, safe
UI copy, and Streamlit rendering with injected state. No test requires a live
API key.

---

## Repository layout

```text
backend/            extraction, retrieval, answer validation, Groq client
frontend/           Streamlit app and UI messages
scripts/            ask_policy.py, evaluate.py, inspect_pdf.py
evaluation/         manually checked question set
tests/              pytest suite
pdfs/               public sample policy wordings
sample_data/        placeholder for local-only sample files (PDFs ignored)
```

---

## Status

Phase 3 local MVP is complete: Streamlit upload -> processing -> question ->
retrieved evidence -> Groq -> validated citations -> verified or manual-review
answer.

Remaining submission work: live deployment, a 3–5 minute demo recording, and the
submission form. Deployment has not been claimed or verified yet.
