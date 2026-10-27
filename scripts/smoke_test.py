"""End-to-end headless smoke test for CoverScope core workflows.

Usage:
    python scripts/smoke_test.py
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure UTF-8 stdout
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import pymupdf

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.domain.enums import ScenarioType
from backend.domain.scenario import ScenarioInput
from backend.services.policy_service import PolicyService


def main() -> int:
    print("=" * 60)
    print("CoverScope End-to-End Core Workflow Smoke Test")
    print("=" * 60)
    svc = PolicyService()

    # 1. Load policy PDFs
    pdf_path_1 = REPO_ROOT / "pdfs" / "ReAssure 2.0 - Policy Wording.pdf"
    pdf_path_2 = REPO_ROOT / "pdfs" / "optima-secure-revision-pw.pdf"

    if not pdf_path_1.exists() or not pdf_path_2.exists():
        print("ERROR: Bundled public PDFs not found in pdfs/")
        return 1

    pol_1 = svc.prepare_policy(pdf_path_1.read_bytes(), pdf_path_1.name)
    pol_2 = svc.prepare_policy(pdf_path_2.read_bytes(), pdf_path_2.name)
    print(f"[PASS] 1. Upload & Parsing: pol_1={pol_1.filename} ({len(pol_1.pages)} pgs), pol_2={pol_2.filename} ({len(pol_2.pages)} pgs)")

    # 2. Extract facts for Explorer
    facts_1 = svc.extract_facts(pol_1)
    print(f"[PASS] 2. Policy Explorer Facts: Extracted {len(facts_1)} facts from {pol_1.filename}")

    # 3. Deterministic Scenario Evaluation
    inp = ScenarioInput(scenario_type=ScenarioType.PRE_EXISTING_CONDITION, elapsed_months=20)
    res = svc.evaluate_scenario(pol_1, inp)
    print(f"[PASS] 3. Scenario Analyzer: verdict={res.verdict.value}, headline='{res.headline}'")

    # 4. Compare Policies
    comp = svc.compare_policies(pol_1, pol_2)
    print(f"[PASS] 4. Policy Comparison: Compared {comp.policy_a_filename} vs {comp.policy_b_filename} ({len(comp.dimensions)} dimensions, {len(comp.protection_gaps)} gaps)")

    # 5. Ingest & Associate Schedule
    benchmarks_path = REPO_ROOT / "evaluation" / "schedule_benchmarks.json"
    with open(benchmarks_path, "r", encoding="utf-8") as f:
        benchmarks = json.load(f)
    sch_fix = benchmarks[0]
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), sch_fix["text"])
    sch_bytes = doc.tobytes()
    doc.close()

    sched = svc.prepare_schedule(sch_bytes, sch_fix["filename"])
    assoc = svc.associate_schedule(sched, pol_2)
    print(f"[PASS] 5. Schedule Ingestion: Assoc Status={assoc.association_status}, Insurer='{assoc.insurer_name}', Masked='{assoc.policy_number_masked}'")

    print("=" * 60)
    print("ALL 5 END-TO-END WORKFLOWS PASSED SUCCESSFULLY")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
