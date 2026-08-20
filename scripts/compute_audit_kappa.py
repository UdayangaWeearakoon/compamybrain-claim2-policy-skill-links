#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step D (part 1): compute Cohen's kappa between the
two independent audit annotators over the 20% link-quality sample.

Per hygiene rule: this is not an LLM-as-judge step that itself scores
Condition A/B (that's Phase 4's job, and would need the 50-hand-labeled-
case validation up front) -- it's the Phase 2 "audit a random 20% sample
by hand, report agreement" step the execution guide calls for. Two
independent subagents (see skill_library/audit/annotator_[ab]_verdicts.json
for their raw output, and the Agent-tool prompts logged in
skill_library/audit/kappa_report.md) each judged the same 23 skills
blind to one another.
"""
import json
import os
from collections import Counter

BASE = os.path.join(os.path.dirname(__file__), "..")
AUDIT_DIR = os.path.join(BASE, "skill_library", "audit")


def main():
    a = json.load(open(os.path.join(AUDIT_DIR, "annotator_a_verdicts.json")))
    b = json.load(open(os.path.join(AUDIT_DIR, "annotator_b_verdicts.json")))
    a_map = {x["skill_id"]: x["verdict"] for x in a}
    b_map = {x["skill_id"]: x["verdict"] for x in b}
    assert set(a_map) == set(b_map), "annotators judged different skill sets"

    ids = list(a_map.keys())
    n = len(ids)
    agree = sum(1 for i in ids if a_map[i] == b_map[i])
    po = agree / n

    ca, cb = Counter(a_map.values()), Counter(b_map.values())
    labels = set(ca) | set(cb)
    pe = sum((ca[k] / n) * (cb[k] / n) for k in labels)
    kappa = 1.0 if pe == 1 else (po - pe) / (1 - pe)

    disagreements = [i for i in ids if a_map[i] != b_map[i]]
    both_no = [i for i in ids if a_map[i] == "no" and b_map[i] == "no"]

    result = {
        "n": n, "observed_agreement": po, "expected_agreement": pe,
        "cohen_kappa": kappa, "disagreements": disagreements,
        "flagged_by_both_annotators": both_no,
        "threshold": 0.8, "passes_threshold": kappa >= 0.8,
    }
    with open(os.path.join(AUDIT_DIR, "kappa_result.json"), "w") as fh:
        json.dump(result, fh, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
