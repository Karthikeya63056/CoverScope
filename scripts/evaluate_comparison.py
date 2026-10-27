"""Auditable offline evaluation harness for CoverScope Policy Comparison and Protection Gaps."""
from __future__ import annotations

import json
from pathlib import Path
import sys

# Ensure repository root is in sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from backend.domain.comparison import ComparisonAssumptions, PolicyComparisonEngine
from backend.domain.enums import ComparisonDimensionKey, ComparisonStatus
from backend.services.policy_service import PolicyService

BENCHMARK_PATH = REPO_ROOT / "evaluation" / "comparison_benchmarks.json"


def run_comparison_evaluation() -> int:
    print("=" * 70)
    print("CoverScope Policy Comparison & Protection Gaps Evaluation Harness")
    print("=" * 70)

    if not BENCHMARK_PATH.exists():
        print(f"Error: Benchmark file {BENCHMARK_PATH} not found.")
        return 1

    with open(BENCHMARK_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)

    service = PolicyService()
    engine = PolicyComparisonEngine()

    policy_cache: dict[str, Any] = {}

    def get_policy(rel_path: str):
        if rel_path not in policy_cache:
            full_path = REPO_ROOT / rel_path
            with open(full_path, "rb") as f:
                data = f.read()
            pol = service.prepare_policy(data, full_path.name)
            policy_cache[rel_path] = pol
        return policy_cache[rel_path]

    total_cases = len(cases)
    passed_cases = 0

    print(f"Loaded {total_cases} auditable comparison benchmark cases.\n")

    for c in cases:
        case_id = c["case_id"]
        desc = c["description"]
        pol_a = get_policy(c["policy_a_file"])
        pol_b = get_policy(c["policy_b_file"])

        ass_data = c.get("assumptions", {})
        assumptions = ComparisonAssumptions(**ass_data)

        result = engine.compare(pol_a, pol_b, assumptions=assumptions)

        dim_key_str = c.get("dimension_key")
        dim_comp = None
        if dim_key_str:
            dim_key = ComparisonDimensionKey(dim_key_str)
            dim_comp = next((d for d in result.dimensions if d.dimension_key == dim_key), None)

        passed = True
        reasons = []

        if "expected_status" in c:
            expected_status = c["expected_status"]
            actual_status = dim_comp.status.value if dim_comp else "MISSING"
            if actual_status != expected_status:
                passed = False
                reasons.append(f"Status mismatch: expected {expected_status}, got {actual_status}")

        if "expected_val_a_amount" in c:
            expected_amt = c["expected_val_a_amount"]
            actual_amt = dim_comp.policy_a_value.numeric_amount if dim_comp else None
            if actual_amt != expected_amt:
                passed = False
                reasons.append(f"Val A amount mismatch: expected {expected_amt}, got {actual_amt}")

        if "expected_val_b_amount" in c:
            expected_amt = c["expected_val_b_amount"]
            actual_amt = dim_comp.policy_b_value.numeric_amount if dim_comp else None
            if actual_amt != expected_amt:
                passed = False
                reasons.append(f"Val B amount mismatch: expected {expected_amt}, got {actual_amt}")

        if "expected_val_a_available" in c:
            if (dim_comp and dim_comp.policy_a_value.is_available) != c["expected_val_a_available"]:
                passed = False
                reasons.append(f"Val A availability mismatch: expected {c['expected_val_a_available']}")

        if "expected_val_b_available" in c:
            if (dim_comp and dim_comp.policy_b_value.is_available) != c["expected_val_b_available"]:
                passed = False
                reasons.append(f"Val B availability mismatch: expected {c['expected_val_b_available']}")

        if "expected_is_identical" in c:
            if result.is_identical_policy != c["expected_is_identical"]:
                passed = False
                reasons.append(f"Identical policy flag mismatch: expected {c['expected_is_identical']}")

        if "expected_gap_dimension" in c:
            exp_dim = c["expected_gap_dimension"]
            matching_gap = next((g for g in result.protection_gaps if g.dimension_key.value == exp_dim), None)
            if not matching_gap:
                passed = False
                reasons.append(f"Expected protection gap for {exp_dim} not found")
            elif "expected_gap_severity" in c and matching_gap.severity.value != c["expected_gap_severity"]:
                passed = False
                reasons.append(f"Gap severity mismatch: expected {c['expected_gap_severity']}, got {matching_gap.severity.value}")

        status_str = "PASS" if passed else "FAIL"
        if passed:
            passed_cases += 1
            print(f"[{status_str}] {case_id}: {desc}")
        else:
            print(f"[{status_str}] {case_id}: {desc} -> {'; '.join(reasons)}")

    print("\n" + "=" * 70)
    print(f"Comparison Benchmark Results: {passed_cases}/{total_cases} cases passed ({passed_cases/total_cases*100:.1f}%)")
    print("=" * 70)
    return 0 if passed_cases == total_cases else 1


if __name__ == "__main__":
    sys.exit(run_comparison_evaluation())
