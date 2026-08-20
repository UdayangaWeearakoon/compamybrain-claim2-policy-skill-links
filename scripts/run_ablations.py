#!/usr/bin/env python3
"""
Claim 2 -- Phase 5, part 3: the two ablations, run regardless of the headline
result.

ABLATION 1 -- link granularity (document- vs section-level).
ABLATION 2 -- remove the negative controls.

Both are scoring-side analyses and are permitted to read ground truth. Neither
feeds anything back into a detector.

A note on what an ablation is for. It is supposed to be able to come out
against the story. Both of these came out other than expected, and both are
reported as measured rather than reshaped:

  * Ablation 1 was expected to show a precision/recall tradeoff between the
    two granularities. On this corpus there is none -- the two arms flag
    IDENTICAL skill sets. The script therefore also measures WHY, so the null
    is diagnosed rather than merely reported.
  * Ablation 2 was expected to show precision inflating when the negative
    controls are removed. For these detectors it cannot: negative controls are
    true negatives (never flagged by either condition), and removing true
    negatives leaves precision algebraically untouched. So the script measures
    the real effect, and then demonstrates the inflation on a detector that
    DOES over-trigger -- which is what actually justifies planting them.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from score_conditions import metrics, bootstrap  # noqa: E402

OUT_DIR = "results/scoring"


def load():
    labels = {r["skill_id"]: r for r in json.load(open("ground_truth/labels.json"))["labels"]}
    b = json.load(open("results/condition_b/flags.json"))
    a = json.load(open("results/condition_a/flags.json"))
    return labels, a, b


def score(skill_ids, labels, flagged, silent=frozenset()):
    pt = metrics(skill_ids, labels, flagged, silent, False)
    ci = bootstrap(skill_ids, labels, flagged, silent, False)
    return {
        "recall": pt["recall"], "precision": pt["precision"],
        "recall_ci": [ci["recall"]["ci_low"], ci["recall"]["ci_high"]],
        "precision_ci": [ci["precision"]["ci_low"], ci["precision"]["ci_high"]],
        "counts": pt["counts"],
    }


# ---------------------------------------------------------------------
# Ablation 1: link granularity
# ---------------------------------------------------------------------
def ablation_granularity(labels, b, skill_ids):
    sec = set(b["section_level"]["flagged_skill_ids"])
    doc = set(b["document_level"]["flagged_skill_ids"])

    arms = {
        "document_level": score(skill_ids, labels, doc),
        "section_level": score(skill_ids, labels, sec),
    }

    # Diagnose the collapse. Section and document differ for a skill only when
    # its policy has a changed rule that the skill does NOT link to, and the
    # skill links to no other changed rule.
    rows = {r["skill_id"]: r for r in b["flags"]}
    links_all_changed = 0        # skill links to every changed rule in its policy
    could_differ = 0             # policy has a changed rule the skill does not link to
    differs = 0
    for sid in skill_ids:
        r = rows[sid]
        if r["policy_id"] is None:
            continue
        changed = set(r["changed_rules_in_policy"])
        linked = set(r["linked_rule_ids"])
        if not changed:
            continue
        if changed <= linked:
            links_all_changed += 1
        else:
            could_differ += 1
        if bool(changed & linked) != bool(changed):
            differs += 1

    return {
        "arms": arms,
        "identical_flag_sets": sec == doc,
        "num_skills_differing": len(sec ^ doc),
        "precision_delta_section_minus_document": (
            arms["section_level"]["precision"] - arms["document_level"]["precision"]
            if arms["section_level"]["precision"] is not None
            and arms["document_level"]["precision"] is not None else None),
        "recall_delta_section_minus_document": (
            arms["section_level"]["recall"] - arms["document_level"]["recall"]),
        "diagnosis": {
            "skills_linking_to_every_changed_rule_in_their_policy": links_all_changed,
            "skills_whose_policy_changed_a_rule_they_do_not_link": could_differ,
            "skills_where_the_two_granularities_actually_differ": differs,
            "explanation": (
                "The two granularities can only diverge for a skill whose policy changed "
                "a rule it does not link to AND which links to no other changed rule. "
                "In this corpus that set is empty: Step 3's in-document cosmetic reword "
                "always lands on the first non-superseded rule, which is a universal "
                "(non-tier-gated) rule present in every skill's dependency link, so every "
                "document-level change also reaches section level. The tradeoff the "
                "ablation is designed to expose therefore has no headroom here. This is a "
                "property of the corpus's rule-sharing density, not evidence that "
                "granularity does not matter -- a corpus whose changes land on "
                "tier-specific or otherwise narrowly-linked rules would separate the two "
                "arms immediately."),
        },
    }


# ---------------------------------------------------------------------
# Ablation 2: remove negative controls
# ---------------------------------------------------------------------
def action_overlap_detector(labels, b, skills):
    """A plausible LINK-FREE alternative to Condition B, used as a
    counterfactual: flag any skill sharing at least one action button with a
    skill that sits under a changed rule.

    This is the kind of behavioural/topical heuristic someone reaches for when
    they have no explicit policy-version-to-skill links -- and it is exactly
    what the negative controls were planted to catch, because cross-cutting
    plumbing (pull up account, notify team) shares actions with almost
    everything.
    """
    sec = set(b["section_level"]["flagged_skill_ids"])
    hot_actions = set()
    for sid in sec:
        hot_actions |= {s["button"] for s in skills[sid]["action_sequence"]}
    return {sid for sid, sk in skills.items()
            if {s["button"] for s in sk["action_sequence"]} & hot_actions}


def ablation_negative_controls(labels, b, skills, skill_ids):
    sec = set(b["section_level"]["flagged_skill_ids"])
    neg = {sid for sid, r in labels.items() if r["policy_id"] is None}
    without = [s for s in skill_ids if s not in neg]

    cond_b_full = score(skill_ids, labels, sec)
    cond_b_without = score(without, labels, sec)

    counter = action_overlap_detector(labels, b, skills)
    counter_full = score(skill_ids, labels, counter)
    counter_without = score(without, labels, counter)

    def delta(a, c):
        if a["precision"] is None or c["precision"] is None:
            return None
        return (c["precision"] - a["precision"]) * 100

    return {
        "num_negative_controls": len(neg),
        "negative_controls_flagged_by_condition_b": sorted(neg & sec),
        "condition_b": {
            "with_negative_controls": cond_b_full,
            "without_negative_controls": cond_b_without,
            "precision_inflation_percentage_points": delta(cond_b_full, cond_b_without),
        },
        "counterfactual_link_free_detector": {
            "description": "flags any skill sharing >=1 action button with a skill under a "
                            "changed rule -- a behavioural/topical heuristic of the kind "
                            "used when no explicit dependency links exist",
            "num_flagged_full_population": counter_full["counts"]["n_flagged"],
            "negative_controls_flagged": len(neg & counter),
            "with_negative_controls": counter_full,
            "without_negative_controls": counter_without,
            "precision_inflation_percentage_points": delta(counter_full, counter_without),
        },
        "interpretation": (
            "Removing the negative controls moves Condition B's precision by exactly 0.0 "
            "points, and this is arithmetic rather than luck: negative controls carry no "
            "dependency link, Condition B never flags them, so they are true negatives, "
            "and precision (TP / flagged) does not read true negatives at all. The "
            "expectation that precision would inflate silently assumes a detector that "
            "fires on them. The counterfactual arm supplies exactly such a detector -- a "
            "link-free action-overlap heuristic -- and there the inflation is real and "
            "measurable. That contrast is the actual justification for planting the "
            "negative controls: they are a falsification test for over-triggering that "
            "Condition B passes and a plausible link-free alternative fails. Had they "
            "been omitted, a detector of the second kind would have looked more precise "
            "than it is, and nothing in the experiment would have exposed it."),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    labels, a, b = load()
    skill_ids = sorted(labels, key=lambda s: int(s.split("-")[1]))

    skills = {}
    import glob
    for f in sorted(glob.glob("skill_library/v1/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d

    g = ablation_granularity(labels, b, skill_ids)
    n = ablation_negative_controls(labels, b, skills, skill_ids)

    result = {
        "phase": 5,
        "note": "Both ablations run regardless of the headline result, per the Phase 5 "
                 "spec. Both came out other than expected and are reported as measured.",
        "ablation_1_link_granularity": g,
        "ablation_2_remove_negative_controls": n,
    }
    with open(f"{OUT_DIR}/ablations.json", "w") as fh:
        json.dump(result, fh, indent=2)

    def f(v, pct=False):
        if v is None:
            return "n/a"
        return f"{v:.1f} pts" if pct else f"{v:.3f}"

    with open(f"{OUT_DIR}/ablations.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ablation", "arm", "recall", "precision", "n_flagged", "n_population"])
        for arm, s in g["arms"].items():
            w.writerow(["link_granularity", arm, f(s["recall"]), f(s["precision"]),
                         s["counts"]["n_flagged"], s["counts"]["n"]])
        for arm, s in [("condition_b_with_negcontrols", n["condition_b"]["with_negative_controls"]),
                        ("condition_b_without_negcontrols", n["condition_b"]["without_negative_controls"]),
                        ("linkfree_counterfactual_with_negcontrols", n["counterfactual_link_free_detector"]["with_negative_controls"]),
                        ("linkfree_counterfactual_without_negcontrols", n["counterfactual_link_free_detector"]["without_negative_controls"])]:
            w.writerow(["remove_negative_controls", arm, f(s["recall"]), f(s["precision"]),
                         s["counts"]["n_flagged"], s["counts"]["n"]])

    print("ABLATION 1 -- link granularity")
    for arm, s in g["arms"].items():
        print(f"  {arm:16s} recall {f(s['recall'])}  precision {f(s['precision'])}  "
              f"flagged {s['counts']['n_flagged']}")
    print(f"  identical flag sets: {g['identical_flag_sets']} "
          f"({g['num_skills_differing']} skills differ)")
    print(f"  diagnosis: {g['diagnosis']['skills_linking_to_every_changed_rule_in_their_policy']} "
          f"skills link to every changed rule in their policy; "
          f"{g['diagnosis']['skills_where_the_two_granularities_actually_differ']} could differ")

    print("\nABLATION 2 -- remove negative controls")
    cb = n["condition_b"]
    print(f"  Condition B   with: precision {f(cb['with_negative_controls']['precision'])}  "
          f"without: {f(cb['without_negative_controls']['precision'])}  "
          f"inflation {f(cb['precision_inflation_percentage_points'], True)}")
    cf = n["counterfactual_link_free_detector"]
    print(f"  link-free CF  with: precision {f(cf['with_negative_controls']['precision'])}  "
          f"without: {f(cf['without_negative_controls']['precision'])}  "
          f"inflation {f(cf['precision_inflation_percentage_points'], True)}")
    print(f"  negative controls flagged -- Condition B: "
          f"{len(n['negative_controls_flagged_by_condition_b'])}, "
          f"link-free counterfactual: {cf['negative_controls_flagged']}")


if __name__ == "__main__":
    main()
