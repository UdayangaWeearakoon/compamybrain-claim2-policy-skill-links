#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step E: structural validator for the v2 corpus +
ground truth label table + sanity anchor, before freezing anything.
Exits non-zero on any failure.
"""
import json
import glob
import re
import sys

FAILS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


def main():
    v1_policies = {json.load(open(f))["policy_id"]: json.load(open(f))
                     for f in glob.glob("policy_corpus/v1/POL-*.json")}
    v2_index = json.load(open("policy_corpus/v2/_v2_index.json"))
    plan = json.load(open("ground_truth/_supersession_plan.json"))
    labels = json.load(open("ground_truth/labels.json"))
    anchor = json.load(open("ground_truth/environment_drift_anchor.json"))

    real_pids = set(v2_index["real_supersession_policies"])
    cosmetic_pids = set(v2_index["cosmetic_only_policies"])
    untouched_pids = set(v2_index["untouched_policies"])
    check(real_pids | cosmetic_pids | untouched_pids == set(v1_policies.keys()),
          "policy partition (real/cosmetic/untouched) doesn't cover all v1 policies exactly once")
    check(not (real_pids & cosmetic_pids), "a policy is both real-supersession and cosmetic-only")

    # every real-supersession policy's v2 file: exactly the planned rule_ids
    # are change_type=real_supersession; nothing else is.
    by_policy_plan = {}
    for a in plan["actions"]:
        by_policy_plan.setdefault(a["policy_id"], set()).add(a["rule_id"])

    for pid in real_pids:
        v2 = json.load(open(f"policy_corpus/v2/{pid}_v2.json"))
        real_in_file = {c["rule_id"] for c in v2["_change_log"] if c["change_type"] == "real_supersession"}
        check(real_in_file == by_policy_plan[pid],
              f"{pid} v2 real_supersession rule_ids {real_in_file} != plan {by_policy_plan[pid]}")
        cosmetic_in_file = [c for c in v2["_change_log"] if c["change_type"] == "cosmetic_reword"]
        check(len(cosmetic_in_file) <= 1, f"{pid} v2 has more than one in-document cosmetic reword")
        # v1/v2 rule_id sets must match (no rules added/removed, only text changed)
        v1_rule_ids = {r["rule_id"] for r in v1_policies[pid]["rules"]}
        v2_rule_ids = {r["rule_id"] for r in v2["rules"]}
        check(v1_rule_ids == v2_rule_ids, f"{pid}: v2 rule_id set != v1 rule_id set")

    for pid in cosmetic_pids:
        v2 = json.load(open(f"policy_corpus/v2/{pid}_v2.json"))
        types = {c["change_type"] for c in v2["_change_log"]}
        check(types == {"cosmetic_reword"}, f"{pid} (cosmetic-only) has a non-cosmetic change: {types}")
        v1_rule_ids = {r["rule_id"] for r in v1_policies[pid]["rules"]}
        v2_rule_ids = {r["rule_id"] for r in v2["rules"]}
        check(v1_rule_ids == v2_rule_ids, f"{pid}: v2 rule_id set != v1 rule_id set")

    for pid in untouched_pids:
        import os
        check(not os.path.exists(f"policy_corpus/v2/{pid}_v2.json"), f"{pid} is untouched but has a v2 file")

    # label table completeness
    all_skill_files = glob.glob("skill_library/v1/SK-*.json")
    check(labels["num_skills"] == len(all_skill_files), "labels.json skill count != skill_library/v1 file count")
    seen_ids = {r["skill_id"] for r in labels["labels"]}
    expected_ids = {json.load(open(f))["skill_id"] for f in all_skill_files}
    check(seen_ids == expected_ids, "labels.json doesn't cover exactly the skill_library/v1 skill_ids")
    for r in labels["labels"]:
        check(r["label"] in ("invalidated", "partial", "valid"), f"{r['skill_id']}: bad label {r['label']}")
        check(bool(r["reason"]), f"{r['skill_id']}: empty reason")

    # negative controls always valid
    neg_rows = [r for r in labels["labels"] if r["policy_id"] is None]
    check(all(r["label"] == "valid" for r in neg_rows), "a negative-control skill has a non-valid label")
    check(len(neg_rows) == labels["num_negative_control"], "negative-control row count mismatch")

    # cosmetic-only / untouched policies' skills must all be valid
    for r in labels["labels"]:
        if r["policy_id"] in cosmetic_pids or r["policy_id"] in untouched_pids:
            check(r["label"] == "valid", f"{r['skill_id']}: policy {r['policy_id']} is "
                   f"cosmetic/untouched but label is {r['label']}")

    # class balance sanity (roughly 40/20/40 target, documented deviation allowed)
    lc = labels["counts_linked_only"]
    total_linked = sum(lc.values())
    check(total_linked == labels["num_linked"], "linked label counts don't sum to num_linked")

    # sanity anchor isolation
    anchor_pids = {s["policy_id"] for s in anchor["impacted_skills"]}
    check(anchor_pids <= untouched_pids, f"sanity anchor policies {anchor_pids} are not all untouched "
           f"(would confound the anchor with a policy-driven label)")
    check(len(anchor["impacted_skills"]) > 0, "sanity anchor has zero impacted skills")

    if FAILS:
        print(f"VALIDATION FAILED ({len(FAILS)} issue(s)):")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("Phase 3 validation PASSED.")
        print(f"  Policies: {len(real_pids)} real-supersession, {len(cosmetic_pids)} cosmetic-only, "
              f"{len(untouched_pids)} untouched (of {len(v1_policies)} total)")
        print(f"  Labels: {labels['counts_full_library']} (full library), "
              f"{labels['counts_linked_only']} (linked only)")
        print(f"  Sanity anchor: '{anchor['anchor_action']}' impacts {len(anchor['impacted_skills'])} "
              f"skills, policies {sorted(anchor_pids)} (confirmed untouched)")


if __name__ == "__main__":
    main()
