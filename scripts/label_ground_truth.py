#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step C: label ground truth per skill, at injection
time, before any detector runs (execution guide requirement).

Label logic, applied per linked skill:
  - Negative-control skills (no policy link by construction) -> Valid.
  - Skill's policy has no v2, or only a cosmetic-only v2 -> Valid (no
    linked rule's testable content changed).
  - Skill's policy has a real-supersession v2:
      intersection = skill.rule_ids  &  {real-superseded rule_ids for that policy}
      - intersection empty                                   -> Valid
      - intersection contains >=1 "hard"-type superseded rule -> Invalidated
      - intersection non-empty, entirely "value_dependent"    -> Partially invalidated

This mirrors exactly the selection logic select_supersessions.py was
designed against -- the plan's achieved_counts should reproduce here
skill-for-skill, which is asserted at the end as a build-time check, not
just an eyeballed match.
"""
import json
import glob
import csv
from collections import defaultdict, Counter

SKILL_DIR = "skill_library/v1"
PLAN_PATH = "ground_truth/_supersession_plan.json"
OUT_DIR = "ground_truth"


def load_skills():
    skills = {}
    for f in sorted(glob.glob(f"{SKILL_DIR}/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d
    return skills


def load_plan():
    return json.load(open(PLAN_PATH))


def main():
    skills = load_skills()
    plan = load_plan()

    # policy_id -> {rule_id: type} for REAL superseded rules only
    superseded_by_policy = defaultdict(dict)
    for a in plan["actions"]:
        superseded_by_policy[a["policy_id"]][a["rule_id"]] = a["type"]

    real_pids = set(plan["real_supersession_policies"])

    rows = []
    for sid in sorted(skills.keys(), key=lambda s: int(s.split("-")[1])):
        s = skills[sid]
        if s["is_negative_control"]:
            rows.append({
                "skill_id": sid, "policy_id": None, "policy_version_v1": None,
                "linked_rule_ids": [], "policy_change_type": "n/a (no policy link)",
                "superseded_rule_ids_hit": [], "supersession_types_hit": [],
                "label": "valid", "reason": "Negative-control skill: no policy dependency link exists by construction.",
            })
            continue

        pid = s["policy_id"]
        rule_ids = set(s["rule_ids"])

        if pid not in real_pids:
            change_type = "real_supersession" if False else (
                "cosmetic_only" if pid else "n/a")
            # determine actual change type for this policy from v2 index below
            rows.append({
                "skill_id": sid, "policy_id": pid, "policy_version_v1": s["policy_version"],
                "linked_rule_ids": sorted(rule_ids), "policy_change_type": None,  # filled below
                "superseded_rule_ids_hit": [], "supersession_types_hit": [],
                "label": "valid", "reason": None,  # filled below
            })
            continue

        hit = {rid: superseded_by_policy[pid][rid] for rid in rule_ids if rid in superseded_by_policy[pid]}
        if not hit:
            label = "valid"
            reason = f"Policy {pid} has a real-supersession v2, but none of this skill's linked rules ({sorted(rule_ids)}) were among the superseded rules."
        elif any(t == "hard" for t in hit.values()):
            hard_rules = [r for r, t in hit.items() if t == "hard"]
            label = "invalidated"
            reason = f"Linked rule(s) {sorted(hard_rules)} superseded by a hard (always-flips) change in {pid} v2 -- this skill's action sequence no longer satisfies the current policy."
        else:
            label = "partial"
            reason = f"Linked rule(s) {sorted(hit.keys())} superseded by value-dependent change(s) in {pid} v2 -- wrong only for inputs on the far side of the new threshold, not universally."
        rows.append({
            "skill_id": sid, "policy_id": pid, "policy_version_v1": s["policy_version"],
            "linked_rule_ids": sorted(rule_ids), "policy_change_type": "real_supersession",
            "superseded_rule_ids_hit": sorted(hit.keys()), "supersession_types_hit": sorted(set(hit.values())),
            "label": label, "reason": reason,
        })

    # fill in policy_change_type / reason for the "not in real_pids" rows
    v2_index = json.load(open("policy_corpus/v2/_v2_index.json"))
    cosmetic_pids = set(v2_index["cosmetic_only_policies"])
    for r in rows:
        if r["reason"] is None:
            pid = r["policy_id"]
            if pid in cosmetic_pids:
                r["policy_change_type"] = "cosmetic_only"
                r["reason"] = f"Policy {pid} received only a cosmetic-only v2 (reword/reorder, no testable content changed) -- correctly not invalidated."
            else:
                r["policy_change_type"] = "none (v1 only)"
                r["reason"] = f"Policy {pid} has no v2 -- unchanged."

    counts = Counter(r["label"] for r in rows)
    linked_rows = [r for r in rows if r["policy_id"] is not None]
    linked_counts = Counter(r["label"] for r in linked_rows)

    # Build-time cross-check against the plan's own achieved_counts (must match
    # exactly, since this script is meant to reproduce that simulation skill-by-skill).
    expected = plan["achieved_counts"]
    assert linked_counts["invalidated"] == expected["invalidated"], \
        f"invalidated mismatch: {linked_counts['invalidated']} vs plan {expected['invalidated']}"
    assert linked_counts["partial"] == expected["partial"], \
        f"partial mismatch: {linked_counts['partial']} vs plan {expected['partial']}"
    assert linked_counts["valid"] == expected["valid"], \
        f"valid mismatch: {linked_counts['valid']} vs plan {expected['valid']}"

    with open(f"{OUT_DIR}/labels.json", "w") as fh:
        json.dump({
            "num_skills": len(rows),
            "num_linked": len(linked_rows),
            "num_negative_control": len(rows) - len(linked_rows),
            "counts_full_library": dict(counts),
            "counts_linked_only": dict(linked_counts),
            "labels": rows,
        }, fh, indent=2)

    with open(f"{OUT_DIR}/labels.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["skill_id", "policy_id", "policy_change_type", "linked_rule_ids",
                     "superseded_rule_ids_hit", "supersession_types_hit", "label", "reason"])
        for r in rows:
            w.writerow([r["skill_id"], r["policy_id"] or "", r["policy_change_type"],
                         ";".join(r["linked_rule_ids"]), ";".join(r["superseded_rule_ids_hit"]),
                         ";".join(r["supersession_types_hit"]), r["label"], r["reason"]])

    print(f"Labeled {len(rows)} skills ({len(linked_rows)} linked, {len(rows)-len(linked_rows)} negative control).")
    print(f"Full library label counts: {dict(counts)}")
    print(f"  as %: " + ", ".join(f"{k}={v/len(rows)*100:.1f}%" for k, v in counts.items()))
    print(f"Linked-only label counts: {dict(linked_counts)}")
    print(f"  as %: " + ", ".join(f"{k}={v/len(linked_rows)*100:.1f}%" for k, v in linked_counts.items()))
    print("Cross-check against supersession plan: OK (exact match)")


if __name__ == "__main__":
    main()
