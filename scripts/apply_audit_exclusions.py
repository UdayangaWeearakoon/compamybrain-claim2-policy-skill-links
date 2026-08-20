#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step D: apply the 20% audit's findings.

Two independent LLM annotators (see skill_library/audit/) reviewed a
random 20% sample of linked skills (seed 20260819) and judged, per skill,
whether its linked policy rules genuinely govern it. Agreement was
perfect (Cohen's kappa = 1.0, well above the 0.8 threshold), so the link
*definition* itself is not ambiguous. But both annotators independently
flagged the same 2 of 23 sampled skills as spurious:

  - SK-053 (POL-016): representative dialogue escalates via Notify
    Internal Team BEFORE attempting Log Out/In or Try Again, the reverse
    of what POL-016-R1 requires, and includes an 'instructions' action
    no linked rule addresses. This is a real ABCD dialogue where the
    human agent deviated from the documented guideline order, not a
    hallucinated action.
  - SK-090 (POL-029): representative dialogue's actions (pull-up-account,
    record-reason, verify-identity, update-account) share no substantive
    action with POL-029's rules (which govern Shipping Status / Validate
    Purchase / Update Order). Manual follow-up traced this to a genuine,
    consistent pattern across all 19 dialogues in that cluster: real
    'manage' (shipping_issue) dialogues in this ABCD release do not
    reliably follow kb.json's documented canonical action sequence for
    that subflow, so the clustering step's "most frequent action
    signature" selection picked a real but off-policy pattern as the
    cluster's representative.

A broader mechanical check (does the skill's final action match ANY
policy-subflow's kb.json-documented terminal action?) was also tried and
rejected: it flagged 47/117 linked skills, the large majority of which
are legitimate early-exit/denial branches or optional steps correctly
skipped (e.g. a membership check ending in denial, never reaching the
gated action) -- not spurious links. Discriminating a genuine early exit
from an actually-mismatched link needs the semantic judgment the audit
step already provides, not a blunter automated filter; see
skill_library/audit/kappa_report.md for the full comparison.

This script removes exactly the 2 audit-confirmed spurious skills,
leaving all skill_ids stable (no renumbering) so the audit trail stays
addressable, and regenerates _skill_index.json and dependency_links.*.
"""
import csv
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
SKILL_DIR = os.path.join(BASE, "skill_library", "v1")
LIB_DIR = os.path.join(BASE, "skill_library")

EXCLUDE = {
    "SK-053": "Both audit annotators: escalates before troubleshooting, reversing "
              "POL-016-R1's required order; includes an action no linked rule covers.",
    "SK-090": "Both audit annotators: action sequence shares no substantive action "
              "with POL-029's rules -- clustering picked an off-policy real dialogue "
              "pattern as the cluster representative.",
}


def main():
    removed = []
    for sid, reason in EXCLUDE.items():
        path = os.path.join(SKILL_DIR, f"{sid}.json")
        if os.path.exists(path):
            os.remove(path)
            removed.append((sid, reason))
        else:
            print(f"WARNING: {sid} not found (already removed?)")

    # rebuild _skill_index.json and dependency_links.{json,csv} from what remains
    skills = []
    for fname in sorted(os.listdir(SKILL_DIR)):
        if fname.startswith("SK-"):
            skills.append(json.load(open(os.path.join(SKILL_DIR, fname))))

    manifest = {
        "num_skills": len(skills),
        "num_linked": sum(1 for s in skills if not s["is_negative_control"]),
        "num_negative_control": sum(1 for s in skills if s["is_negative_control"]),
        "audit_exclusions_applied": [{"skill_id": s, "reason": r} for s, r in removed],
        "skills": [
            {"skill_id": s["skill_id"], "file": f"{s['skill_id']}.json",
             "policy_id": s["policy_id"], "subflow": s["subflow"],
             "branch": s["branch"], "is_negative_control": s["is_negative_control"]}
            for s in skills
        ],
    }
    with open(os.path.join(SKILL_DIR, "_skill_index.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    links = [{
        "skill_id": s["skill_id"], "policy_id": s["policy_id"],
        "policy_version": s["policy_version"], "rule_ids": s["rule_ids"],
        "is_negative_control": s["is_negative_control"], "branch": s["branch"],
    } for s in skills]
    with open(os.path.join(LIB_DIR, "dependency_links.json"), "w") as fh:
        json.dump({"num_skills": len(links),
                    "num_linked": sum(1 for l in links if not l["is_negative_control"]),
                    "num_negative_control": sum(1 for l in links if l["is_negative_control"]),
                    "links": links}, fh, indent=2)
    with open(os.path.join(LIB_DIR, "dependency_links.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["skill_id", "policy_id", "policy_version", "rule_ids", "branch", "is_negative_control"])
        for l in links:
            w.writerow([l["skill_id"], l["policy_id"] or "", l["policy_version"] or "",
                        ";".join(l["rule_ids"]), l["branch"] or "", l["is_negative_control"]])

    print(f"Removed {len(removed)} audit-confirmed spurious skills: {[s for s, _ in removed]}")
    print(f"Remaining: {manifest['num_skills']} total "
          f"({manifest['num_linked']} linked, {manifest['num_negative_control']} negative control)")


if __name__ == "__main__":
    main()
