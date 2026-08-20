#!/usr/bin/env python3
"""
Claim 2 -- Phase 4, silent wrong action rate.

Guide: "Take invalidated skills that each condition failed to flag. Execute
them against ABCD gold action sequences under the v2 policy. Every execution
that completes without error but produces the wrong action is a silent wrong
action. This converts a detection miss into a demonstrated operational harm."

Procedure fixed in preregistration/STEP4_PREREGISTRATION.md section 4.

For each INVALIDATED skill a condition did not flag, replay its recorded gold
action sequence:

  1. EXECUTION CHECK -- validate the sequence against the v2 environment
     contract, reusing Condition A's check-set verbatim (imported, not
     reimplemented, so "executes cleanly" means exactly what the baseline
     means by it). Failing here is a LOUD error, not a silent one.
  2. CORRECTNESS CHECK -- evaluate the sequence against a deterministic
     compliance predicate for every v2 rule that superseded one of the
     skill's linked rules.
  3. Passes (1) and fails (2)  ->  SILENT WRONG ACTION.

No LLM-as-judge is used: every predicate below is a deterministic function of
recorded data, so the guide's 50-hand-labeled-case judge validation is not
applicable by construction (stated in the preregistration before this ran).

THIS IS A SCORING-SIDE SCRIPT. Unlike the two conditions, it is permitted to
read ground_truth/ -- that is what "invalidated skills that each condition
failed to flag" requires. It never feeds anything back into either condition;
both flag tables are read as finished, frozen inputs.
"""
import csv
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from run_condition_a import load_contract, validate_skill  # noqa: E402

SKILL_DIR = "skill_library/v1"
OUT_DIR = "results/silent_wrong_action"

VERIFY_HARDENED = {
    "POL-005-R1", "POL-006-R1", "POL-007-R1", "POL-008-R1",
    "POL-009-R1", "POL-010-R1", "POL-011-R1", "POL-012-R1",
}
VALIDATE_HARDENED = {"POL-001-R1", "POL-002-R1", "POL-003-R1"}


def predicate_min_values(seq, action, n):
    """Compliant iff some `action` step supplies >= n values."""
    calls = [s for s in seq if s["button"] == action]
    if not calls:
        return None, f"no '{action}' step in the recorded sequence"
    best = max(len(s["values"]) for s in calls)
    if best >= n:
        return True, f"'{action}' supplies {best} values (>= {n} required by v2)"
    return False, (f"'{action}' supplies only {best} value(s); v2 requires {n} "
                    f"(the added field is never collected)")


def predicate_absent_action(seq, action, why):
    """Compliant iff `action` does NOT appear (v2 forbids reaching it)."""
    if any(s["button"] == action for s in seq):
        return False, f"sequence still calls '{action}', which v2 forbids: {why}"
    return True, f"sequence does not call '{action}' -- consistent with v2"


def evaluate_rule(rule_id, skill):
    """Deterministic v2-compliance predicate for one superseded hard rule.
    Returns (compliant: bool|None, explanation). None == predicate not
    applicable to this skill."""
    seq = skill["action_sequence"]

    if rule_id in VERIFY_HARDENED:
        return predicate_min_values(seq, "verify-identity", 4)
    if rule_id in VALIDATE_HARDENED:
        return predicate_min_values(seq, "validate-purchase", 4)
    if rule_id == "POL-004-R3":
        return predicate_absent_action(
            seq, "update-order",
            "guest members are never eligible for a return in v2, so the "
            "return-granting step must not be reached")
    if rule_id == "POL-035-R3":
        return predicate_absent_action(
            seq, "ask-the-oracle",
            "Bronze/Guest are always denied in v2 and the Oracle is no longer "
            "consulted for these tiers")
    return None, f"no predicate defined for {rule_id}"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    skills = {}
    for f in sorted(glob.glob(f"{SKILL_DIR}/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d

    labels = {r["skill_id"]: r for r in json.load(open("ground_truth/labels.json"))["labels"]}
    invalidated = [sid for sid, r in labels.items() if r["label"] == "invalidated"]

    a_flags = json.load(open("results/condition_a/flags.json"))
    b_flags = json.load(open("results/condition_b/flags.json"))
    flagged = {
        "A": set(a_flags["v2_primary"]["flagged_skill_ids"]),
        "B_section": set(b_flags["section_level"]["flagged_skill_ids"]),
    }

    v1c = load_contract("v1")
    v2c = load_contract("v2")

    per_condition = {}
    execution_log = []

    for cond, flagged_ids in flagged.items():
        missed = sorted([s for s in invalidated if s not in flagged_ids],
                         key=lambda s: int(s.split("-")[1]))
        silent, errored, compliant_anyway = [], [], []

        for sid in missed:
            skill = skills[sid]

            # 1. execution check -- Condition A's own check-set, imported
            violations = validate_skill(skill, v2c, v1c)
            executes_cleanly = not violations

            # 2. correctness check
            superseded_hit = labels[sid]["superseded_rule_ids_hit"]
            rule_results = []
            for rid in superseded_hit:
                ok, why = evaluate_rule(rid, skill)
                rule_results.append({"rule_id": rid, "compliant": ok, "explanation": why})

            decided = [r for r in rule_results if r["compliant"] is not None]
            violates_v2 = any(r["compliant"] is False for r in decided)

            if not executes_cleanly:
                outcome = "errored_loudly"
                errored.append(sid)
            elif violates_v2:
                outcome = "silent_wrong_action"
                silent.append(sid)
            else:
                outcome = "executed_and_compliant"
                compliant_anyway.append(sid)

            execution_log.append({
                "condition": cond, "skill_id": sid,
                "ground_truth_label": labels[sid]["label"],
                "flagged_by_condition": False,
                "superseded_rules_hit": superseded_hit,
                "execution_errors": violations,
                "executes_cleanly": executes_cleanly,
                "rule_compliance": rule_results,
                "violates_v2_policy": violates_v2,
                "outcome": outcome,
            })

        undecided = [r for r in execution_log
                      if r["condition"] == cond
                      and all(x["compliant"] is None for x in r["rule_compliance"])]

        per_condition[cond] = {
            "num_invalidated": len(invalidated),
            "num_flagged_by_condition": len(flagged_ids),
            "num_invalidated_missed": len(missed),
            "missed_skill_ids": missed,
            "num_silent_wrong_action": len(silent),
            "silent_wrong_action_skill_ids": silent,
            "num_errored_loudly": len(errored),
            "num_executed_and_compliant": len(compliant_anyway),
            "num_no_predicate_applicable": len(undecided),
        }

    result = {
        "measurement": "silent wrong action rate",
        "procedure_ref": "preregistration/STEP4_PREREGISTRATION.md section 4",
        "definition": "an invalidated skill a condition failed to flag, whose recorded "
                       "gold action sequence executes cleanly against the v2 environment "
                       "contract but violates a v2 policy rule that superseded one of its "
                       "linked rules",
        "judge": "deterministic predicates only -- no LLM-as-judge, so the guide's "
                  "50-hand-labeled-case judge validation is not applicable by construction",
        "note": "Raw counts only. The rate itself (silent / invalidated) and its "
                 "confidence interval are computed in Step 5.",
        "num_invalidated_total": len(invalidated),
        "per_condition": per_condition,
        "execution_log": execution_log,
    }

    with open(f"{OUT_DIR}/silent_wrong_action.json", "w") as fh:
        json.dump(result, fh, indent=2)

    with open(f"{OUT_DIR}/execution_log.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "skill_id", "ground_truth_label", "superseded_rules_hit",
                     "executes_cleanly", "violates_v2_policy", "outcome", "explanation"])
        for r in execution_log:
            expl = " | ".join(f"{x['rule_id']}: {x['explanation']}" for x in r["rule_compliance"])
            w.writerow([r["condition"], r["skill_id"], r["ground_truth_label"],
                         ";".join(r["superseded_rules_hit"]), r["executes_cleanly"],
                         r["violates_v2_policy"], r["outcome"], expl])

    print(f"Silent wrong action -- {len(invalidated)} invalidated skills in ground truth")
    for cond, s in per_condition.items():
        print(f"  Condition {cond}:")
        print(f"    missed invalidated        : {s['num_invalidated_missed']}")
        print(f"    -> silent wrong actions   : {s['num_silent_wrong_action']}")
        print(f"    -> errored loudly         : {s['num_errored_loudly']}")
        print(f"    -> executed and compliant : {s['num_executed_and_compliant']}")
        if s["num_no_predicate_applicable"]:
            print(f"    !! no predicate applicable: {s['num_no_predicate_applicable']}")


if __name__ == "__main__":
    main()
