#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step D: the sanity-anchor environment drift case.

Execution guide: "Add one environment drift case as a sanity anchor.
Change one API contract somewhere. SKILLGUARD must catch it and your
dependency detector need not. This single case proves both detectors
work as designed and that they watch different things."

The "API contract" analog in this substrate is ABCD's ontology.json
action-argument schema (data/ontology.json -> "actions"): for each tool
button, the list of argument slots it accepts. This is the environment
contract SKILLGUARD-style validation checks skills against -- completely
independent of policy text.

Anchor choice: the `select-faq` tool (used by 6 skills, all under POL-036
/ POL-037 -- both of which never receive any v2 in this phase, real or
cosmetic). That isolation is deliberate: this case must be clean, not
entangled with any policy-driven label, or it stops proving what it's
meant to prove. v1 signature: ['single_item_query', 'storewide_query'].
v2 signature: adds a new required argument, 'topic_category_id' -- a
genuine tool-contract change with nothing to do with any policy.

Expected Step 4 outcome (not run here -- this step only builds and
freezes the artifact):
  - Condition A (SKILLGUARD-style contract validation): flags all 6
    select-faq skills, since their recorded calls don't supply the new
    required argument. This is what the baseline is FOR.
  - Condition B (dependency-link detector): does not flag them, and
    should not -- POL-036/POL-037 are untouched, so no policy-version
    link changed. Ground truth label for all 6 stays "valid" in
    ground_truth/labels.json, same as any other skill under an untouched
    policy.
"""
import json
import glob

ONTOLOGY_PATH = "/mnt/user-data/uploads/CB/abcd-master/data/ontology.json"
OUT_DIR = "ground_truth"
SKILL_DIR = "skill_library/v1"

ANCHOR_ACTION = "select-faq"
NEW_ARG = "topic_category_id"


def main():
    ontology = json.load(open(ONTOLOGY_PATH))
    actions_by_category = ontology["actions"]

    v1_schema = {}
    for category, actions in actions_by_category.items():
        for action, args in actions.items():
            v1_schema[action] = {"category": category, "args": args}

    assert ANCHOR_ACTION in v1_schema, f"{ANCHOR_ACTION} not found in ontology.json actions"

    v2_schema = json.loads(json.dumps(v1_schema))  # deep copy
    v2_schema[ANCHOR_ACTION]["args"] = v1_schema[ANCHOR_ACTION]["args"] + [NEW_ARG]

    import os
    os.makedirs("environment_contracts", exist_ok=True)

    with open("environment_contracts/v1_action_schemas.json", "w") as fh:
        json.dump({
            "source": "ABCD ontology.json (Chen et al. 2021, arXiv 2104.00783), 'actions' field",
            "version": "v1", "effective_timestamp": "2021-06-01T00:00:00Z",
            "schema": v1_schema,
        }, fh, indent=2)

    with open("environment_contracts/v2_action_schemas.json", "w") as fh:
        json.dump({
            "source": "Synthetic sanity-anchor edit for Claim 2 Phase 3 (not from ABCD)",
            "version": "v2", "effective_timestamp": "2026-01-15T00:00:00Z",
            "supersedes": "v1",
            "changed_actions": [ANCHOR_ACTION],
            "schema": v2_schema,
        }, fh, indent=2)

    # find the impacted skills
    skills = {}
    for f in sorted(glob.glob(f"{SKILL_DIR}/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d

    impacted = []
    for sid, s in skills.items():
        if s["is_negative_control"]:
            continue
        buttons = {step["button"] for step in s["action_sequence"]}
        if ANCHOR_ACTION in buttons:
            impacted.append({"skill_id": sid, "policy_id": s["policy_id"]})

    anchor = {
        "case_name": "environment_drift_sanity_anchor",
        "anchor_action": ANCHOR_ACTION,
        "v1_args": v1_schema[ANCHOR_ACTION]["args"],
        "v2_args": v2_schema[ANCHOR_ACTION]["args"],
        "change_description": f"'{ANCHOR_ACTION}' gains a new required argument, '{NEW_ARG}', "
                                f"in v2 -- a pure environment/tool-contract change with no "
                                f"corresponding policy text change anywhere.",
        "isolation_note": "Both policies these skills are linked to (POL-036, POL-037) are "
                            "untouched in policy_corpus/v2 (no v1->v2 document at all) -- this "
                            "case cannot be confounded with a policy-driven label.",
        "impacted_skills": impacted,
        "expected_condition_a_behavior": "Flags all impacted skills (contract violation: recorded "
                                            "calls omit the new required argument).",
        "expected_condition_b_behavior": "Does not flag them (no policy version changed for "
                                            "POL-036/POL-037); ground_truth label for all impacted "
                                            "skills is 'valid'.",
        "not_run_here": "Actually running Condition A/B against this case is Step 4 scope; this "
                          "artifact only builds and freezes the case for that step to consume.",
    }
    with open(f"{OUT_DIR}/environment_drift_anchor.json", "w") as fh:
        json.dump(anchor, fh, indent=2)

    print(f"Anchor action: {ANCHOR_ACTION}")
    print(f"v1 args: {v1_schema[ANCHOR_ACTION]['args']}")
    print(f"v2 args: {v2_schema[ANCHOR_ACTION]['args']}")
    print(f"Impacted skills ({len(impacted)}): {[s['skill_id'] for s in impacted]}")
    print(f"Impacted policies: {sorted(set(s['policy_id'] for s in impacted))}")
    print("Wrote environment_contracts/v1_action_schemas.json, v2_action_schemas.json, "
          "ground_truth/environment_drift_anchor.json")


if __name__ == "__main__":
    main()
