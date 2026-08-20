#!/usr/bin/env python3
"""
Claim 2 -- Phase 4, Condition A: SKILLGUARD-style environment-contract
validation (the baseline).

Procedure fixed in preregistration/STEP4_PREREGISTRATION.md section 2.
Every skill's recorded action_sequence is validated against a target
environment contract version. Three structural checks:

  A1  unknown action        -- button absent from the contract
  A2  arity overflow        -- more values supplied than the action permits
  A3  unsatisfied newly-introduced parameter
                            -- the action's current signature contains a
                               parameter absent from the signature the skill
                               was authored against; a recorded call is an
                               unlabeled positional value list and so provides
                               no binding for a parameter that did not exist
                               when it was recorded

The run does BOTH:
  * v1 control  -- expected 0 flags. A validator that flags skills under the
                   very contract version they were distilled from is broken;
                   this control is the evidence that A1-A3 are calibrated, not
                   arbitrarily permissive (prereg 2, "baseline strength").
  * v2 primary  -- the actual Condition A result.

A fourth candidate check (value-domain conformance against
ontology.json values.enumerable) was prototyped and EXCLUDED on measured
evidence: 151 false positives under v1, because ABCD stores action arguments
as an untyped positional value list while an action's arg list mixes
enumerable slots with free-text ones, so an address or account ID gets scored
against an enumerable vocabulary and fails spuriously. Full reasoning and the
measured count are in the preregistration, recorded before this ran.

ISOLATION: reads skill_library/ and environment_contracts/ only. It does not
read policy_corpus/, ground_truth/, or the anchor description -- Condition A
is not permitted to know which skills a policy change touched, or which case
is the planted anchor.
"""
import csv
import glob
import json
import os

SKILL_DIR = "skill_library/v1"
CONTRACT_DIR = "environment_contracts"
OUT_DIR = "results/condition_a"


def load_skills():
    skills = {}
    for f in sorted(glob.glob(f"{SKILL_DIR}/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d
    return skills


def load_contract(version):
    path = os.path.join(CONTRACT_DIR, f"{version}_action_schemas.json")
    return json.load(open(path))["schema"]


def validate_skill(skill, contract, baseline_contract):
    """Return list of violation dicts for one skill. Empty list == passes.

    baseline_contract is the signature set the skill was authored against
    (v1). When validating against v1 itself, baseline == contract, so A3 can
    never fire -- which is exactly why the v1 control is a meaningful check.
    """
    violations = []
    for idx, step in enumerate(skill["action_sequence"]):
        button = step["button"]
        values = step["values"]

        # A1 -- unknown action
        if button not in contract:
            violations.append({
                "step_index": idx, "action": button, "check": "A1_unknown_action",
                "detail": f"action '{button}' is absent from the current environment contract",
            })
            continue

        args = contract[button]["args"]

        # A2 -- arity overflow
        if len(values) > len(args):
            violations.append({
                "step_index": idx, "action": button, "check": "A2_arity_overflow",
                "detail": f"call supplies {len(values)} values but the contract permits "
                          f"at most {len(args)} ({args})",
            })

        # A3 -- unsatisfied newly-introduced parameter
        base_args = baseline_contract.get(button, {}).get("args", args)
        new_params = [a for a in args if a not in base_args]
        if new_params:
            violations.append({
                "step_index": idx, "action": button,
                "check": "A3_unsatisfied_new_parameter",
                "detail": f"signature gained parameter(s) {new_params} not present when this "
                          f"call was recorded; the recorded positional value list "
                          f"({len(values)} value(s)) provides no binding for them",
            })
    return violations


def run(target_version, contract, baseline_contract, skills):
    rows = []
    for sid in sorted(skills, key=lambda s: int(s.split("-")[1])):
        v = validate_skill(skills[sid], contract, baseline_contract)
        rows.append({
            "skill_id": sid,
            "flagged": bool(v),
            "num_violations": len(v),
            "violated_checks": sorted({x["check"] for x in v}),
            "violations": v,
        })
    return rows


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    skills = load_skills()
    v1 = load_contract("v1")
    v2 = load_contract("v2")

    # --- v1 control: baseline == target, A3 structurally cannot fire ---
    control = run("v1", v1, v1, skills)
    control_flagged = [r["skill_id"] for r in control if r["flagged"]]

    # --- v2 primary run ---
    primary = run("v2", v2, v1, skills)
    primary_flagged = [r["skill_id"] for r in primary if r["flagged"]]

    control_ok = len(control_flagged) == 0

    result = {
        "condition": "A",
        "description": "SKILLGUARD-style environment-contract validation",
        "procedure_ref": "preregistration/STEP4_PREREGISTRATION.md section 2",
        "checks": ["A1_unknown_action", "A2_arity_overflow", "A3_unsatisfied_new_parameter"],
        "excluded_check": {
            "name": "value_domain_conformance",
            "reason": "151 false positives under v1; ABCD stores action arguments as an "
                       "untyped positional value list while an action's arg list mixes "
                       "enumerable and free-text slots, so free-text values are scored "
                       "against enumerable vocabularies and fail spuriously",
            "measured_v1_false_positives": 151,
        },
        "population": len(skills),
        "v1_control": {
            "purpose": "calibration evidence that the check-set is not arbitrarily "
                        "permissive or arbitrarily strict; a validator that flags skills "
                        "under the contract version they were distilled from is broken",
            "num_flagged": len(control_flagged),
            "flagged_skill_ids": control_flagged,
            "expected_num_flagged": 0,
            "control_passed": control_ok,
        },
        "v2_primary": {
            "num_flagged": len(primary_flagged),
            "flagged_skill_ids": primary_flagged,
        },
        "flags": primary,
    }

    with open(f"{OUT_DIR}/flags.json", "w") as fh:
        json.dump(result, fh, indent=2)

    with open(f"{OUT_DIR}/flags.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["skill_id", "flagged", "num_violations", "violated_checks", "detail"])
        for r in primary:
            w.writerow([r["skill_id"], r["flagged"], r["num_violations"],
                         ";".join(r["violated_checks"]),
                         " | ".join(x["detail"] for x in r["violations"])])

    with open(f"{OUT_DIR}/control_v1_flags.json", "w") as fh:
        json.dump({"num_flagged": len(control_flagged),
                    "flagged_skill_ids": control_flagged,
                    "control_passed": control_ok,
                    "flags": control}, fh, indent=2)

    print(f"Condition A -- population {len(skills)} skills")
    print(f"  v1 control : {len(control_flagged)} flagged (expected 0) -- "
          f"{'PASS' if control_ok else 'FAIL'}")
    print(f"  v2 primary : {len(primary_flagged)} flagged")
    print(f"    {primary_flagged}")
    if not control_ok:
        raise SystemExit("v1 control failed -- check-set is miscalibrated, refusing to "
                          "present the v2 result as a valid baseline")


if __name__ == "__main__":
    main()
