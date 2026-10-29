import re

def detect_claim_citation_contradiction(quote: str, answer: str) -> str | None:
    quote_lower = quote.lower()
    answer_lower = answer.lower()

    # 1. Duration contradiction: e.g. quote has "36 months" but answer asserts "24 months"
    # Extract duration units from quote: e.g. "36 months", "30 days", "12 months", "24 months"
    quote_durations = re.findall(r"(\b\d+\b)\s*(month|months|day|days|year|years)", quote_lower)
    answer_durations = re.findall(r"(\b\d+\b)\s*(month|months|day|days|year|years)", answer_lower)

    if quote_durations and answer_durations:
        # Map unit types
        def norm_unit(u):
            return "month" if "month" in u else ("day" if "day" in u else "year")
        
        q_dur_by_unit = {}
        for num, u in quote_durations:
            q_dur_by_unit.setdefault(norm_unit(u), set()).add(int(num))

        a_dur_by_unit = {}
        for num, u in answer_durations:
            a_dur_by_unit.setdefault(norm_unit(u), set()).add(int(num))

        for unit, q_nums in q_dur_by_unit.items():
            if unit in a_dur_by_unit:
                a_nums = a_dur_by_unit[unit]
                # If there is no overlap in durations of the same unit between quote and answer
                # (e.g. quote says only 36 months, answer says only 24 months)
                if not (q_nums & a_nums):
                    return f"Citation duration ({q_nums} {unit}s) contradicts answer duration ({a_nums} {unit}s)"

    # 2. Percentage contradiction: e.g. quote says "10%" but answer asserts "20%"
    q_pcts = set(re.findall(r"(\b\d+\b)\s*%", quote_lower))
    a_pcts = set(re.findall(r"(\b\d+\b)\s*%", answer_lower))
    if q_pcts and a_pcts and not (q_pcts & a_pcts):
        return f"Citation percentage ({q_pcts}%) contradicts answer percentage ({a_pcts}%)"

    return None

# Test 1: Contradicting duration
q1 = "Bariatric Surgery: 36 months"
a1_bad = "The waiting period for bariatric surgery is 24 months."
print("Test 1 (bad):", detect_claim_citation_contradiction(q1, a1_bad))

a1_good = "The waiting period for bariatric surgery is 36 months."
print("Test 1 (good):", detect_claim_citation_contradiction(q1, a1_good))

# Test 2: TC-5 where answer has both 36 and 12 months
q2 = "Upon purchase of this optional cover, the PED Waiting Period reduces from 36 months to 12 months."
a2 = "The standard pre-existing disease waiting period is 36 months. It can be reduced to 12 months if the optional cover is purchased."
print("Test 2 (TC-5):", detect_claim_citation_contradiction(q2, a2))

# Test 3: Contradicting percentage
q3 = "This policy is subject to Co-payment of 10% of each and every claim amount"
a3_bad = "The co-payment for entry age 61+ is 20%."
print("Test 3 (bad):", detect_claim_citation_contradiction(q3, a3_bad))

a3_good = "A co-payment of 10% applies for insured persons aged 61 and above at entry."
print("Test 3 (good):", detect_claim_citation_contradiction(q3, a3_good))
