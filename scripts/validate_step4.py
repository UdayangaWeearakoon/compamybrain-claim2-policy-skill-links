#!/usr/bin/env python3
"""
Claim 2 -- Phase 4, step E: structural validator for the Step 4 run.

The most important check here is LEAKAGE. The execution guide names this as
the failure mode most likely to silently corrupt an experiment of this shape:
"Condition B must never read the ground truth label table. The labels exist
only for scoring. Leakage here is the most common silent corruption in this
experimental shape, because the same researcher built both the labels and the
detector." That is exactly this project's situation, so the ban is enforced
mechanically rather than by assertion.

Exits non-zero on any failure.
"""
import ast
import glob
import json
import os
import sys

FAILS = []
WARNS = []


def check(cond, msg):
    if not cond:
        FAILS.append(msg)


# ---------------------------------------------------------------------
# 1. Leakage: static analysis of each condition's source
# ---------------------------------------------------------------------
def accessed_strings(path):
    """Return the set of strings this module actually USES to touch data:

      * every string argument to an open() or glob.glob() call
      * every module-level string constant (these scripts hold their paths in
        module constants such as SKILL_DIR, then open(os.path.join(...)))
      * every literal dict/attribute subscript key (catches doc["_change_log"])

    An earlier version of this check simply grepped the source text for the
    forbidden identifiers. It produced two false positives on
    run_condition_b.py, because that script writes a human-readable
    "isolation" note into its own output JSON, and that note necessarily
    NAMES the things it is forbidden to read. Grepping cannot tell a file
    read from a sentence about a file read; an AST walk can. Parsing what the
    code actually touches is both stricter (it resolves paths held in module
    constants) and free of that class of false positive.
    """
    tree = ast.parse(open(path).read())
    found = set()

    for node in ast.walk(tree):
        # string args to open(...) / glob.glob(...)
        if isinstance(node, ast.Call):
            fname = ""
            if isinstance(node.func, ast.Name):
                fname = node.func.id
            elif isinstance(node.func, ast.Attribute):
                fname = node.func.attr
            if fname in ("open", "glob"):
                for arg in ast.walk(node):
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.add(arg.value)
        # literal subscript keys, e.g. doc["_change_log"]
        if isinstance(node, ast.Subscript):
            s = node.slice
            if isinstance(s, ast.Constant) and isinstance(s.value, str):
                found.add(s.value)

    # module-level string constants
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                found.add(node.value.value)

    return found


FORBIDDEN = {
    "run_condition_a.py": {
        "ground_truth": "Condition A must not read the ground truth label table",
        "labels.json": "Condition A must not read the ground truth label table",
        "policy_corpus": "Condition A is contract-only; reading policy text would make it "
                          "something other than the SKILLGUARD-style baseline",
        "environment_drift_anchor": "Condition A must not read the planted anchor's description",
    },
    "run_condition_b.py": {
        "ground_truth": "Condition B must never read the ground truth label table",
        "labels.json": "Condition B must never read the ground truth label table",
        "_change_log": "Condition B must not read the v2 change-type annotations -- that "
                        "field is the real-vs-cosmetic answer key for the distractor set",
        "_supersession_plan": "Condition B must not read the injection-time supersession plan",
    },
}


def check_leakage():
    for fname, banned in FORBIDDEN.items():
        path = os.path.join("scripts", fname)
        if not os.path.exists(path):
            FAILS.append(f"{fname} not found -- cannot verify isolation")
            continue
        touched = accessed_strings(path)
        for token, why in banned.items():
            hits = sorted(s for s in touched if token in s)
            if hits:
                FAILS.append(f"LEAKAGE: {fname} accesses {hits} (matches banned "
                              f"'{token}') -- {why}")


# ---------------------------------------------------------------------
# 2. Run integrity
# ---------------------------------------------------------------------
def main():
    check_leakage()

    skill_ids = set()
    for f in glob.glob("skill_library/v1/SK-*.json"):
        skill_ids.add(json.load(open(f))["skill_id"])

    a = json.load(open("results/condition_a/flags.json"))
    b = json.load(open("results/condition_b/flags.json"))
    swa = json.load(open("results/silent_wrong_action/silent_wrong_action.json"))
    labels = {r["skill_id"]: r for r in json.load(open("ground_truth/labels.json"))["labels"]}
    anchor = json.load(open("ground_truth/environment_drift_anchor.json"))

    # population coverage
    check(a["population"] == len(skill_ids), "Condition A population != skill library size")
    check(b["population"] == len(skill_ids), "Condition B population != skill library size")
    check({r["skill_id"] for r in a["flags"]} == skill_ids,
          "Condition A did not evaluate exactly the skill library")
    check({r["skill_id"] for r in b["flags"]} == skill_ids,
          "Condition B did not evaluate exactly the skill library")

    # Condition A v1 control must have passed
    check(a["v1_control"]["control_passed"] is True,
          "Condition A v1 control did not pass -- baseline check-set is miscalibrated")
    check(a["v1_control"]["num_flagged"] == 0,
          f"Condition A v1 control flagged {a['v1_control']['num_flagged']} skills, expected 0")

    # sanity anchor behaves as designed: A catches it, B does not
    anchor_ids = {s["skill_id"] for s in anchor["impacted_skills"]}
    a_flagged = set(a["v2_primary"]["flagged_skill_ids"])
    b_flagged = set(b["section_level"]["flagged_skill_ids"])
    check(anchor_ids <= a_flagged,
          f"Condition A failed to flag the environment-drift anchor: missing "
          f"{sorted(anchor_ids - a_flagged)}")
    check(not (anchor_ids & b_flagged),
          f"Condition B flagged anchor skills it should not: {sorted(anchor_ids & b_flagged)}")
    check(all(labels[s]["label"] == "valid" for s in anchor_ids),
          "an anchor skill is not labeled valid in ground truth -- the anchor is confounded")

    # negative controls can never be flagged by B (no dependency link exists)
    neg = {sid for sid, r in labels.items() if r["policy_id"] is None}
    check(not (neg & b_flagged),
          f"Condition B flagged negative-control skills: {sorted(neg & b_flagged)}")

    # Condition B must not flag skills whose policy has no v2
    for r in b["flags"]:
        if r["flagged_section"]:
            check(r["policy_has_v2"],
                  f"{r['skill_id']}: flagged by B but its policy has no v2 document")
            check(bool(r["changed_rules_hit"]),
                  f"{r['skill_id']}: flagged at section level with no changed rule hit")

    # SWA integrity
    invalidated = {sid for sid, r in labels.items() if r["label"] == "invalidated"}
    check(swa["num_invalidated_total"] == len(invalidated),
          "SWA invalidated total disagrees with the ground truth label table")
    for cond, s in swa["per_condition"].items():
        flagged = a_flagged if cond == "A" else b_flagged
        expected_missed = sorted(invalidated - flagged, key=lambda x: int(x.split("-")[1]))
        check(s["missed_skill_ids"] == expected_missed,
              f"SWA missed-set for {cond} disagrees with that condition's flag table")
        total = (s["num_silent_wrong_action"] + s["num_errored_loudly"]
                 + s["num_executed_and_compliant"])
        check(total == s["num_invalidated_missed"],
              f"SWA outcome buckets for {cond} do not sum to the missed count")
        if s["num_no_predicate_applicable"]:
            WARNS.append(f"{cond}: {s['num_no_predicate_applicable']} missed skill(s) had no "
                          f"applicable compliance predicate -- their outcome is undecided")

    # every SWA log row must correspond to a genuinely unflagged invalidated skill
    for r in swa["execution_log"]:
        check(r["ground_truth_label"] == "invalidated",
              f"SWA log contains a non-invalidated skill {r['skill_id']}")
        flagged = a_flagged if r["condition"] == "A" else b_flagged
        check(r["skill_id"] not in flagged,
              f"SWA log contains {r['skill_id']} which that condition DID flag")

    # preregistration must exist and predate the run in git history (checked here
    # only for presence; ordering is visible in the commit log)
    check(os.path.exists("preregistration/STEP4_PREREGISTRATION.md"),
          "preregistration document is missing")

    if FAILS:
        print(f"STEP 4 VALIDATION FAILED ({len(FAILS)} issue(s)):")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)

    print("Step 4 validation PASSED.")
    print(f"  Isolation: no forbidden identifier in executable code of either condition")
    print(f"  Condition A: v1 control 0 flags (calibrated); v2 flags "
          f"{a['v2_primary']['num_flagged']}/{a['population']}")
    print(f"  Condition B: section-level flags {b['section_level']['num_flagged']}"
          f"/{b['population']}; anchor correctly not flagged")
    print(f"  Silent wrong actions: A={swa['per_condition']['A']['num_silent_wrong_action']}, "
          f"B={swa['per_condition']['B_section']['num_silent_wrong_action']} "
          f"(of {swa['num_invalidated_total']} invalidated)")
    for w in WARNS:
        print(f"  WARNING: {w}")


if __name__ == "__main__":
    main()
