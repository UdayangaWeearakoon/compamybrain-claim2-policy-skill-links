#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step C: structural validation of the distilled skill
library. Substitutes for literal per-skill human review (see
skill_library/CONSTRUCTION.md for why, same disclosed-limitation pattern
as Phase 1's deterministic-template substitution for an LLM rewriting
pass): every skill is checked against a fixed, auditable set of
structural criteria rather than eyeballed one at a time.

Checks:
  - skill_id uniqueness
  - every rule_id referenced actually exists in the referenced policy
  - policy_id/policy_version is either a real frozen v1 policy, or the
    skill is explicitly marked is_negative_control with policy_id=None
  - non-negative-control skills have >=1 rule_id (a "linked" skill with
    zero rules would be a data bug, not a real negative control)
  - action_sequence is non-empty
  - provenance convo_ids actually exist in the extracted action-trace set
    (i.e. are real ABCD dialogues, not fabricated)
  - precondition/postcondition are non-empty and not template-degenerate
    (e.g. didn't fall through to an unfilled placeholder)
"""
import json
import os

BASE = os.path.join(os.path.dirname(__file__), "..")
SKILL_DIR = os.path.join(BASE, "skill_library", "v1")
POLICY_DIR = os.path.join(BASE, "policy_corpus", "v1")
TRACES_PATH = os.path.join(BASE, "skill_library", "intermediate", "action_traces.json")


def main():
    policies = {}
    for fname in os.listdir(POLICY_DIR):
        if fname.startswith("POL-"):
            d = json.load(open(os.path.join(POLICY_DIR, fname)))
            policies[d["policy_id"]] = {r["rule_id"] for r in d["rules"]}

    traces = json.load(open(TRACES_PATH))
    known_convo_ids = {r["convo_id"] for r in traces["records"]}

    skill_files = sorted(f for f in os.listdir(SKILL_DIR) if f.startswith("SK-"))
    errors = []
    seen_ids = set()

    for fname in skill_files:
        sk = json.load(open(os.path.join(SKILL_DIR, fname)))
        sid = sk["skill_id"]

        if sid in seen_ids:
            errors.append(f"{sid}: duplicate skill_id")
        seen_ids.add(sid)

        if sk["is_negative_control"]:
            if sk["policy_id"] is not None or sk["rule_ids"]:
                errors.append(f"{sid}: negative control must have policy_id=None and rule_ids=[]")
        else:
            if sk["policy_id"] not in policies:
                errors.append(f"{sid}: unknown policy_id {sk['policy_id']}")
            elif not sk["rule_ids"]:
                errors.append(f"{sid}: linked skill has zero rule_ids")
            else:
                bad_rules = [rid for rid in sk["rule_ids"] if rid not in policies[sk["policy_id"]]]
                if bad_rules:
                    errors.append(f"{sid}: rule_ids not found in {sk['policy_id']}: {bad_rules}")

        if not sk["action_sequence"]:
            errors.append(f"{sid}: empty action_sequence")

        for cid in sk["provenance_convo_ids"]:
            if cid not in known_convo_ids:
                errors.append(f"{sid}: provenance convo_id {cid} not found in extracted traces")

        if not sk["precondition"] or not sk["precondition"].strip():
            errors.append(f"{sid}: empty precondition")
        if not sk["postcondition"] or not sk["postcondition"].strip():
            errors.append(f"{sid}: empty postcondition")
        if "{" in sk["precondition"] or "{" in sk["postcondition"]:
            errors.append(f"{sid}: unfilled template placeholder in precondition/postcondition")

    print(f"Validated {len(skill_files)} skill files.")
    if errors:
        print(f"FAILED: {len(errors)} structural errors found:")
        for e in errors[:50]:
            print(" -", e)
        raise SystemExit(1)
    else:
        print("PASSED: no structural errors.")


if __name__ == "__main__":
    main()
