#!/usr/bin/env python3
"""
Claim 2 -- Phase 4, Condition B: policy-version-to-skill dependency-link
detector (the intervention).

Procedure fixed in preregistration/STEP4_PREREGISTRATION.md section 3.

For each policy carrying a v2 document, compare v1 and v2 rule statements by
rule_id. Any rule whose statement text differs is a CHANGED RULE. Follow the
Phase 2 dependency link table from each changed rule to the skills recorded
under it, and flag those skills.

Two granularities are emitted:
  B-section  (PRIMARY)  flag iff >=1 rule_id in the skill's own dependency
                        link changed -- the guide's "follow the dependency
                        links from the changed policy sections to the skills
                        distilled under them"
  B-document (ABLATION INPUT) flag iff ANY rule in the linked policy document
                        changed. Emitted as raw output only; the guide assigns
                        the granularity comparison to Step 5, so no comparison
                        is drawn here.

DELIBERATELY NAIVE. Per the guide: "Implement the simplest version first: any
linked skill under a superseded section gets flagged." This detector makes no
attempt to tell a substantive rule change from a cosmetic reword -- it sees
only that the linked rule's text differs. The Step 3 distractors (5
cosmetic-only policies, plus one in-document cosmetic reword inside each of
the 18 real-supersession policies) are therefore expected to cost real
precision. That loss is the measurement the distractors were planted to
produce; suppressing it would be the experiment marking its own homework.

======================================================================
ISOLATION -- what this script is forbidden to read, and why
======================================================================
1. ground_truth/ (labels.json, labels.csv, _supersession_plan.json).
   The labels exist only for scoring. A detector that reads them is not a
   detector.
2. The `_change_log` field inside each v2 policy document. That field carries
   change_type: real_supersession | cosmetic_reword -- injection-time metadata
   that IS the answer key for the distractor set. Reading it would let
   Condition B skip exactly the cosmetic edits it is supposed to be fooled by,
   manufacturing precision it did not earn.

load_rules() below therefore extracts ONLY rule_id and statement, discarding
every other key, so _change_log cannot leak in even accidentally.
scripts/validate_step4.py greps this file for "ground_truth", "labels", and
"_change_log" and fails the build if any appears outside this comment block.
======================================================================
"""
import csv
import glob
import json
import os

POLICY_V1_DIR = "policy_corpus/v1"
POLICY_V2_DIR = "policy_corpus/v2"
LINK_TABLE = "skill_library/dependency_links.json"
OUT_DIR = "results/condition_b"


def load_rules(path):
    """Load ONLY {rule_id: statement} from a policy document.

    Every other field -- including the injection-time change annotations -- is
    discarded here at the boundary, so no downstream code can reach it.
    """
    doc = json.load(open(path))
    return {r["rule_id"]: r["statement"] for r in doc["rules"]}


def detect_changed_rules():
    """Diff v1 vs v2 rule text per policy. Returns:
        changed_rules_by_policy: policy_id -> set of changed rule_ids
        policies_with_v2:        set of policy_ids having a v2 document
    """
    changed_by_policy = {}
    policies_with_v2 = set()

    for v2_path in sorted(glob.glob(f"{POLICY_V2_DIR}/POL-*_v2.json")):
        policy_id = os.path.basename(v2_path).split("_")[0]
        v1_path = None
        for cand in sorted(glob.glob(f"{POLICY_V1_DIR}/{policy_id}_*.json")):
            v1_path = cand
            break
        if v1_path is None:
            # a v2 with no v1 would be a new policy, not a supersession
            continue

        policies_with_v2.add(policy_id)
        v1_rules = load_rules(v1_path)
        v2_rules = load_rules(v2_path)

        changed = set()
        for rid, v2_text in v2_rules.items():
            v1_text = v1_rules.get(rid)
            if v1_text is None:
                changed.add(rid)          # rule introduced in v2
            elif v1_text != v2_text:
                changed.add(rid)          # rule text differs
        for rid in v1_rules:
            if rid not in v2_rules:
                changed.add(rid)          # rule removed in v2
        changed_by_policy[policy_id] = changed

    return changed_by_policy, policies_with_v2


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    changed_by_policy, policies_with_v2 = detect_changed_rules()
    links = json.load(open(LINK_TABLE))["links"]

    rows = []
    for link in links:
        sid = link["skill_id"]
        pid = link["policy_id"]
        linked_rules = set(link["rule_ids"])

        if pid is None:
            # negative-control skill: no policy dependency link exists, so no
            # policy change can reach it by construction
            rows.append({
                "skill_id": sid, "policy_id": None, "linked_rule_ids": [],
                "policy_has_v2": False, "changed_rules_in_policy": [],
                "changed_rules_hit": [], "flagged_section": False,
                "flagged_document": False,
                "rationale": "No dependency link (negative control): no policy version "
                              "change can propagate to this skill.",
            })
            continue

        changed_in_policy = changed_by_policy.get(pid, set())
        hit = sorted(linked_rules & changed_in_policy)

        flagged_section = bool(hit)
        flagged_document = bool(changed_in_policy)

        if flagged_section:
            rationale = (f"Linked rule(s) {hit} changed between {pid} v1 and v2 -- "
                          f"skill was distilled under superseded text.")
        elif flagged_document:
            rationale = (f"{pid} changed in v2, but none of this skill's own linked "
                          f"rules {sorted(linked_rules)} did (document-level only).")
        elif pid in policies_with_v2:
            rationale = f"{pid} has a v2 but no rule text differs."
        else:
            rationale = f"{pid} has no v2 document -- unchanged."

        rows.append({
            "skill_id": sid, "policy_id": pid,
            "linked_rule_ids": sorted(linked_rules),
            "policy_has_v2": pid in policies_with_v2,
            "changed_rules_in_policy": sorted(changed_in_policy),
            "changed_rules_hit": hit,
            "flagged_section": flagged_section,
            "flagged_document": flagged_document,
            "rationale": rationale,
        })

    rows.sort(key=lambda r: int(r["skill_id"].split("-")[1]))
    sec_flagged = [r["skill_id"] for r in rows if r["flagged_section"]]
    doc_flagged = [r["skill_id"] for r in rows if r["flagged_document"]]

    total_changed_rules = sum(len(v) for v in changed_by_policy.values())

    result = {
        "condition": "B",
        "description": "policy-version-to-skill dependency-link detector",
        "procedure_ref": "preregistration/STEP4_PREREGISTRATION.md section 3",
        "granularities": {
            "section": "PRIMARY -- flag iff a rule in the skill's own dependency link changed",
            "document": "ABLATION INPUT -- flag iff any rule in the linked policy changed; "
                         "comparison deferred to Step 5",
        },
        "isolation": "Reads only policy rule text (rule_id + statement) and the Phase 2 "
                      "dependency link table. Never reads ground_truth/ or the v2 "
                      "_change_log real-vs-cosmetic annotations.",
        "naivety_note": "Detects that linked rule text differs; makes no attempt to "
                          "distinguish a substantive change from a cosmetic reword. "
                          "Precision loss on the planted distractors is expected and is "
                          "the honest measurement.",
        "population": len(rows),
        "policies_with_v2": sorted(policies_with_v2),
        "num_policies_with_v2": len(policies_with_v2),
        "num_changed_rules_detected": total_changed_rules,
        "changed_rules_by_policy": {k: sorted(v) for k, v in sorted(changed_by_policy.items())},
        "section_level": {"num_flagged": len(sec_flagged), "flagged_skill_ids": sec_flagged},
        "document_level": {"num_flagged": len(doc_flagged), "flagged_skill_ids": doc_flagged},
        # Self-observation over this condition's own output only (no ground truth,
        # no change-type metadata). Surfaced because Step 5's planned granularity
        # ablation depends on these two differing.
        "granularity_agreement": {
            "identical": sec_flagged == doc_flagged,
            "num_differing_skills": len(
                set(sec_flagged) ^ set(doc_flagged)),
            "note": "If identical, the section-vs-document granularity ablation has no "
                     "headroom on this corpus and Step 5 should report that as a "
                     "structural finding rather than a null effect.",
        },
        "flags": rows,
    }

    with open(f"{OUT_DIR}/flags.json", "w") as fh:
        json.dump(result, fh, indent=2)

    with open(f"{OUT_DIR}/flags.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["skill_id", "policy_id", "linked_rule_ids", "policy_has_v2",
                     "changed_rules_hit", "flagged_section", "flagged_document", "rationale"])
        for r in rows:
            w.writerow([r["skill_id"], r["policy_id"] or "", ";".join(r["linked_rule_ids"]),
                         r["policy_has_v2"], ";".join(r["changed_rules_hit"]),
                         r["flagged_section"], r["flagged_document"], r["rationale"]])

    print(f"Condition B -- population {len(rows)} skills")
    print(f"  policies with a v2 document : {len(policies_with_v2)}")
    print(f"  changed rules detected      : {total_changed_rules}")
    print(f"  section-level flagged (PRIMARY) : {len(sec_flagged)}")
    print(f"  document-level flagged (ablation): {len(doc_flagged)}")


if __name__ == "__main__":
    main()
