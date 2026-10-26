# CoverScope — Phase 1 starter

This starter implements the first vertical slice of document processing:
- PDF validation
- page-by-page text extraction with PyMuPDF
- basic scan/empty-page quality checks
- configurable extracted-character limit (provisional until sample PDFs are measured)
- page-based chunk IDs (`P12-C1`, `P12-C2`, ...)
- no overlap in model-context chunks
- extraction diagnostics for inspecting table-heavy pages
- tests for chunk IDs, limits, and extraction helpers

## 1. Setup

Python 3.11+ recommended.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Inspect a policy PDF

```powershell
python scripts/inspect_pdf.py "path\to\public-policy.pdf"
```

The script reports page count, extracted character count, per-page text length, likely text-poor pages, and pages with many text blocks that may deserve table inspection.

**Do not treat the default 400,000-character limit as final.** It is configurable and provisional. Inspect two or three sample PDFs, record their extracted sizes, then set a threshold compatible with both the observed data and the selected model's context/cost limits.

## 3. Run tests

```powershell
pytest -q
```

## 4. Important limitations

- OCR is not implemented. Scanned/image-only PDFs are rejected with an actionable error.
- PyMuPDF's text extraction may scramble table layout. The inspection script flags pages for manual review; it does not claim table extraction is correct.
- The first extraction path uses sorted text, then sorted text blocks as a diagnostic fallback for pages where the text result is sparse. Table-specific parsing is not automatic. If a benefit table is garbled, inspect `page.get_text("blocks", sort=True)` output and try `pdfplumber` for that table/page before proceeding.
- This is Phase 1 only. It does not yet call an LLM or produce coverage verdicts.
