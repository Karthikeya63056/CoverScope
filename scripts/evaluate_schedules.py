"""Auditable offline evaluation harness for CoverScope Policy Schedule Ingestion and Association."""
from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure UTF-8 output even on Windows consoles
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
import pymupdf

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.domain.enums import DocumentAssociationStatus
from backend.services.policy_service import PolicyService

BENCHMARK_PATH = REPO_ROOT / "evaluation" / "schedule_benchmarks.json"


def make_pdf(text: str) -> bytes:
    doc = pymupdf.open()
    p = doc.new_page()
    p.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def run_schedule_evaluation() -> int:
    print("=" * 70)
    print("CoverScope Policy Schedule Ingestion & Association Evaluation Harness")
    print("=" * 70)

    if not BENCHMARK_PATH.exists():
        print(f"Error: Benchmark file {BENCHMARK_PATH} not found.")
        return 1

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    service = PolicyService()
    policy_cache: dict[str, Any] = {}

    def get_wording_policy(rel_path: str):
        if rel_path not in policy_cache:
            full_path = REPO_ROOT / rel_path
            with open(full_path, "rb") as f:
                data = f.read()
            pol = service.prepare_policy(data, full_path.name)
            policy_cache[rel_path] = pol
        return policy_cache[rel_path]

    total_cases = len(cases)
    passed_cases = 0

    print(f"Loaded {total_cases} synthetic schedule test fixtures.\n")
    print("NOTICE: Evaluates deterministic extractor accuracy and conflict detection on representative")
    print("synthetic schedule formats. Real-world schedule validation remains ongoing.\n")

    for c in cases:
        fixture_id = c["fixture_id"]
        desc = c["description"]
        text = c["text"]
        pdf_bytes = make_pdf(text)

        schedule = service.prepare_schedule(pdf_bytes, c["filename"])
        target_policy = get_wording_policy(c["target_wording_file"])
        associated = service.associate_schedule(schedule, target_policy)

        passed = True
        reasons = []

        if c.get("expected_insurer") and schedule.insurer_name != c["expected_insurer"]:
            passed = False
            reasons.append(f"Insurer mismatch: expected {c['expected_insurer']}, got {schedule.insurer_name}")

        if c.get("expected_product") and schedule.product_name != c["expected_product"]:
            passed = False
            reasons.append(f"Product mismatch: expected {c['expected_product']}, got {schedule.product_name}")

        if c.get("expected_inception") and schedule.inception_date != c["expected_inception"]:
            passed = False
            reasons.append(f"Inception mismatch: expected {c['expected_inception']}, got {schedule.inception_date}")

        if c.get("expected_expiry") and schedule.expiry_date != c["expected_expiry"]:
            passed = False
            reasons.append(f"Expiry mismatch: expected {c['expected_expiry']}, got {schedule.expiry_date}")

        if c.get("expected_sum_insured") and schedule.sum_insured != c["expected_sum_insured"]:
            passed = False
            reasons.append(f"Sum Insured mismatch: expected {c['expected_sum_insured']}, got {schedule.sum_insured}")

        if c.get("expected_member_count") is not None and len(schedule.members) != c["expected_member_count"]:
            passed = False
            reasons.append(f"Member count mismatch: expected {c['expected_member_count']}, got {len(schedule.members)}")

        if c.get("expected_rider_count") is not None and len(schedule.optional_riders) != c["expected_rider_count"]:
            passed = False
            reasons.append(f"Rider count mismatch: expected {c['expected_rider_count']}, got {len(schedule.optional_riders)}")

        if c.get("expected_association_status") and associated.association_status.value != c["expected_association_status"]:
            passed = False
            reasons.append(f"Association mismatch: expected {c['expected_association_status']}, got {associated.association_status.value}")

        status_str = "PASS" if passed else "FAIL"
        if passed:
            passed_cases += 1
            print(f"[{status_str}] {fixture_id}: {desc}")
            print(f"       Policy: {schedule.policy_number_masked or 'N/A'} | Members: {len(schedule.members)} | Assoc: {associated.association_status.value}")
        else:
            print(f"[{status_str}] {fixture_id}: {desc} -> {'; '.join(reasons)}")

    print("\n" + "=" * 70)
    print(f"Schedule Evaluation Results: {passed_cases}/{total_cases} fixtures passed ({passed_cases/total_cases*100:.1f}%)")
    print("=" * 70)
    return 0 if passed_cases == total_cases else 1


if __name__ == "__main__":
    sys.exit(run_schedule_evaluation())
