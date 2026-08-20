#!/usr/bin/env python3
"""
Claim 2 -- Phase 5, part 2: slice Condition B's errors by class.

Run BEFORE any interpretation is written, so the interpretation follows the
slice rather than the slice being assembled to support a story already told.

The Phase 5 spec anticipates that partial invalidation dominates Condition B's
errors, because section-level links blur when only some rules in a section
change. This script tests that expectation rather than assuming it, and
records the answer either way -- including the direction the error mass
actually takes, which is not the one the word "misses" implies.

An "error" here is any skill on which the condition disagrees with the
PRIMARY scoring convention (partial as a separate, non-positive class):
  * false negative -- invalidated, not flagged
  * false positive -- flagged, not invalidated (this includes every flagged
                      partial skill, by that convention)
"""
import csv
import json
import os
from collections import Counter

OUT_DIR = "results/scoring"


def main():
    labels = {r["skill_id"]: r for r in json.load(open("ground_truth/labels.json"))["labels"]}
    b = json.load(open("results/condition_b/flags.json"))
    b_rows = {r["skill_id"]: r for r in b["flags"]}
    flagged = set(b["section_level"]["flagged_skill_ids"])

    false_negatives, false_positives = [], []
    for sid, lab in labels.items():
        is_pos = lab["label"] == "invalidated"
        is_flagged = sid in flagged
        if is_pos and not is_flagged:
            false_negatives.append(sid)
        elif is_flagged and not is_pos:
            false_positives.append(sid)

    keyfn = lambda s: int(s.split("-")[1])
    false_negatives.sort(key=keyfn)
    false_positives.sort(key=keyfn)

    def describe(sid):
        lab, row = labels[sid], b_rows[sid]
        return {
            "skill_id": sid,
            "true_label": lab["label"],
            "policy_id": lab["policy_id"],
            "policy_change_type": lab["policy_change_type"],
            "supersession_types_hit": lab["supersession_types_hit"],
            "superseded_rule_ids_hit": lab["superseded_rule_ids_hit"],
            "linked_rule_ids": lab["linked_rule_ids"],
            "changed_rules_in_policy": row["changed_rules_in_policy"],
            "changed_rules_hit": row["changed_rules_hit"],
            "detector_rationale": row["rationale"],
        }

    fp_detail = [describe(s) for s in false_positives]
    fn_detail = [describe(s) for s in false_negatives]

    fp_by_class = Counter(d["true_label"] for d in fp_detail)
    fp_by_change = Counter(d["policy_change_type"] for d in fp_detail)

    # For flagged partial skills: which of their linked rules changed, and
    # which did not -- the blur the spec predicts.
    partial_fp = [d for d in fp_detail if d["true_label"] == "partial"]
    blur_evidence = []
    for d in partial_fp:
        linked = set(d["linked_rule_ids"])
        changed_hit = set(d["changed_rules_hit"])
        blur_evidence.append({
            "skill_id": d["skill_id"],
            "num_linked_rules": len(linked),
            "num_linked_rules_changed": len(changed_hit),
            "linked_rules_unchanged": sorted(linked - changed_hit),
            "supersession_types_hit": d["supersession_types_hit"],
            "partial_because": "only some linked rules changed, and the change that landed "
                                "is value-dependent (wrong only for inputs past the new "
                                "threshold), so the skill is not universally invalid -- but "
                                "a section-level link cannot express 'this rule changed, "
                                "but only for some inputs'",
        })

    n_partial_all = sum(1 for r in labels.values() if r["label"] == "partial")
    n_partial_flagged = sum(1 for s, r in labels.items()
                            if r["label"] == "partial" and s in flagged)
    total_errors = len(fp_detail) + len(fn_detail)
    partial_share = (len(partial_fp) / total_errors) if total_errors else None

    result = {
        "condition": "B (dependency links, section-level)",
        "scoring_convention": "PRIMARY -- partial is a separate, non-positive class, so a "
                               "flagged partial skill counts as a false positive",
        "totals": {
            "population": len(labels),
            "flagged": len(flagged),
            "false_negatives": len(fn_detail),
            "false_positives": len(fp_detail),
            "total_errors": total_errors,
        },
        "headline": {
            "false_negative_count": len(fn_detail),
            "false_negatives_are_zero": len(fn_detail) == 0,
            "error_mass_is_entirely_false_positive": len(fn_detail) == 0 and len(fp_detail) > 0,
            "partial_class_share_of_error_mass": partial_share,
            "partial_dominates_error_mass": (partial_share or 0) > 0.5,
            "partial_class_flagged": f"{n_partial_flagged}/{n_partial_all}",
        },
        "false_positives_by_true_label": dict(fp_by_class),
        "false_positives_by_policy_change_type": dict(fp_by_change),
        "partial_blur_evidence": blur_evidence,
        "false_positive_detail": fp_detail,
        "false_negative_detail": fn_detail,
    }

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(f"{OUT_DIR}/condition_b_error_slice.json", "w") as fh:
        json.dump(result, fh, indent=2)

    with open(f"{OUT_DIR}/condition_b_error_slice.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["error_type", "skill_id", "true_label", "policy_id",
                     "policy_change_type", "supersession_types_hit",
                     "linked_rule_ids", "changed_rules_hit"])
        for etype, detail in (("false_negative", fn_detail), ("false_positive", fp_detail)):
            for d in detail:
                w.writerow([etype, d["skill_id"], d["true_label"], d["policy_id"],
                             d["policy_change_type"], ";".join(d["supersession_types_hit"]),
                             ";".join(d["linked_rule_ids"]), ";".join(d["changed_rules_hit"])])

    print("Condition B error slice (primary convention)")
    print(f"  population {len(labels)}, flagged {len(flagged)}")
    print(f"  false negatives : {len(fn_detail)}")
    print(f"  false positives : {len(fp_detail)}")
    print(f"  FP by true label : {dict(fp_by_class)}")
    print(f"  FP by change type: {dict(fp_by_change)}")
    if total_errors:
        print(f"  partial share of total error mass: {partial_share:.1%} "
              f"({len(partial_fp)}/{total_errors}) -- "
              f"{'DOMINATES' if partial_share > 0.5 else 'does not dominate'}")


if __name__ == "__main__":
    main()
