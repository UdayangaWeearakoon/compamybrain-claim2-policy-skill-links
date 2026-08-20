#!/usr/bin/env python3
"""
Claim 2 -- Phase 5, part 1: score both conditions against the frozen labels.

Builds the main results table -- invalidation recall, invalidation precision,
and silent wrong action rate per condition -- with bootstrap confidence
intervals (1000 resamples over skills), then applies the preregistered
threshold mechanically.

Every metric definition and the decision rule were fixed in
preregistration/STEP4_PREREGISTRATION.md (sections 5 and 6) BEFORE either
condition ran. This script implements them; it does not get to choose them.
That is the point of preregistering: by the time the numbers exist, there is
no discretion left to exercise.

  invalidation recall    = |flagged & invalidated| / |invalidated|
  invalidation precision = |flagged & invalidated| / |flagged|
  silent wrong action    = |silent wrong actions| / |invalidated|

PRIMARY scoring treats `partial` as a SEPARATE class -- it is NOT folded into
`invalidated`. A partial skill flagged by a condition therefore counts against
precision. This is deliberately the harsh reading and it was fixed in advance
precisely so it could not be relaxed once it started costing Condition B
points. The partial-inclusive variant is reported alongside as the
preregistered secondary cut, never as a replacement.

Seed is fixed (hygiene rule #3). This is the first Phase where randomness
enters at all -- everything in Phase 4 was deterministic.
"""
import csv
import json
import os
import random

SEED = 20260820
N_BOOT = 1000
OUT_DIR = "results/scoring"


def load():
    labels = {r["skill_id"]: r for r in json.load(open("ground_truth/labels.json"))["labels"]}
    a = json.load(open("results/condition_a/flags.json"))
    b = json.load(open("results/condition_b/flags.json"))
    swa = json.load(open("results/silent_wrong_action/silent_wrong_action.json"))
    return labels, a, b, swa


def metrics(skill_ids, labels, flagged, silent_set, partial_counts_as_positive=False):
    """Compute the three metrics over an arbitrary (possibly resampled) list of
    skill ids. Returns None for a metric whose denominator is empty."""
    positive = {"invalidated", "partial"} if partial_counts_as_positive else {"invalidated"}

    n_pos = sum(1 for s in skill_ids if labels[s]["label"] in positive)
    n_flagged = sum(1 for s in skill_ids if s in flagged)
    n_tp = sum(1 for s in skill_ids if s in flagged and labels[s]["label"] in positive)

    # silent wrong action is defined over the invalidated class only, per the
    # guide's wording ("invalidated skills that each condition failed to flag"),
    # regardless of the partial-inclusive variant
    n_inval = sum(1 for s in skill_ids if labels[s]["label"] == "invalidated")
    n_silent = sum(1 for s in skill_ids if s in silent_set)

    return {
        "recall": (n_tp / n_pos) if n_pos else None,
        "precision": (n_tp / n_flagged) if n_flagged else None,
        "silent_wrong_action_rate": (n_silent / n_inval) if n_inval else None,
        "counts": {"n": len(skill_ids), "n_positive": n_pos, "n_flagged": n_flagged,
                    "n_true_positive": n_tp, "n_invalidated": n_inval,
                    "n_silent_wrong_action": n_silent},
    }


def bootstrap(skill_ids, labels, flagged, silent_set, partial_inclusive):
    """Percentile bootstrap over skills. Resamples with replacement N_BOOT times.

    A resample can leave a metric undefined (e.g. it happens to contain no
    flagged skill, so precision has no denominator). Those draws are excluded
    from that metric's interval and COUNTED, rather than silently coerced to 0
    or 1 -- coercing would quietly bias the interval toward whichever value was
    chosen.
    """
    rng = random.Random(SEED)
    n = len(skill_ids)
    acc = {"recall": [], "precision": [], "silent_wrong_action_rate": []}
    undefined = {"recall": 0, "precision": 0, "silent_wrong_action_rate": 0}

    for _ in range(N_BOOT):
        draw = [skill_ids[rng.randrange(n)] for _ in range(n)]
        m = metrics(draw, labels, flagged, silent_set, partial_inclusive)
        for k in acc:
            if m[k] is None:
                undefined[k] += 1
            else:
                acc[k].append(m[k])

    out = {}
    for k, vals in acc.items():
        if not vals:
            out[k] = {"ci_low": None, "ci_high": None, "n_effective": 0,
                       "n_undefined_resamples": undefined[k]}
            continue
        vals.sort()
        lo = vals[int(0.025 * (len(vals) - 1))]
        hi = vals[int(0.975 * (len(vals) - 1))]
        out[k] = {"ci_low": lo, "ci_high": hi, "n_effective": len(vals),
                   "n_undefined_resamples": undefined[k]}
    return out


def score_condition(name, skill_ids, labels, flagged, silent_set):
    row = {"condition": name}
    for variant, partial_inclusive in [("primary", False), ("partial_inclusive", True)]:
        point = metrics(skill_ids, labels, flagged, silent_set, partial_inclusive)
        ci = bootstrap(skill_ids, labels, flagged, silent_set, partial_inclusive)
        row[variant] = {
            "point": {k: point[k] for k in
                       ("recall", "precision", "silent_wrong_action_rate")},
            "ci": ci,
            "counts": point["counts"],
        }
    return row


def fmt(v):
    return "n/a" if v is None else f"{v:.3f}"


def fmt_ci(m, key):
    c = m["ci"][key]
    if c["ci_low"] is None:
        return "n/a"
    return f"[{c['ci_low']:.3f}, {c['ci_high']:.3f}]"


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    labels, a, b, swa = load()
    skill_ids = sorted(labels, key=lambda s: int(s.split("-")[1]))

    flags = {
        "A (SKILLGUARD contract validation)": set(a["v2_primary"]["flagged_skill_ids"]),
        "B (dependency links, section-level)": set(b["section_level"]["flagged_skill_ids"]),
    }
    silent = {
        "A (SKILLGUARD contract validation)":
            set(swa["per_condition"]["A"]["silent_wrong_action_skill_ids"]),
        "B (dependency links, section-level)":
            set(swa["per_condition"]["B_section"]["silent_wrong_action_skill_ids"]),
    }

    rows = [score_condition(name, skill_ids, labels, flags[name], silent[name])
            for name in flags]

    # ---- preregistered decision rule, applied mechanically ----
    ra = rows[0]["primary"]["point"]["recall"]
    rb = rows[1]["primary"]["point"]["recall"]
    pa = rows[0]["primary"]["point"]["precision"]
    pb = rows[1]["primary"]["point"]["precision"]

    recall_improved = rb > ra
    precision_drop_pts = (pa - pb) * 100 if (pa is not None and pb is not None) else None
    precision_within_bound = (precision_drop_pts is not None and precision_drop_pts <= 5.0)

    if not recall_improved:
        verdict = "FAILS"
        why = "Condition B did not improve invalidation recall over Condition A."
    elif precision_within_bound:
        verdict = "HOLDS"
        why = ("Condition B improves invalidation recall over Condition A, and its "
               "precision does not drop more than the preregistered 5-point bound.")
    else:
        verdict = "PARTIAL"
        why = ("Condition B improves invalidation recall, but its precision drop exceeds "
               "the preregistered 5-point bound.")

    decision = {
        "rule_source": "preregistration/STEP4_PREREGISTRATION.md section 6, fixed before "
                        "either condition ran; itself derived from the team claims file "
                        "('fails if dependency links add no recall over contract "
                        "validation; holds if they catch supersession cases contracts "
                        "miss, at comparable precision')",
        "recall_A": ra, "recall_B": rb, "recall_improved": recall_improved,
        "precision_A": pa, "precision_B": pb,
        "precision_drop_percentage_points": precision_drop_pts,
        "precision_bound_percentage_points": 5.0,
        "precision_within_bound": precision_within_bound,
        "verdict": verdict,
        "explanation": why,
        "degenerate_precision_note": (
            "Condition A's precision is 0.000 because it made zero true-positive "
            "invalidation detections while flagging 6 skills. Those 6 flags are its "
            "CORRECT environment-drift detections (the sanity anchor), which the "
            "invalidation label set scores as non-positives because no policy governing "
            "them changed. Condition A is not malfunctioning; it is being measured on an "
            "axis it does not observe. This is the orthogonality the claim rests on, and "
            "it is why the precision-drop test is satisfied trivially here rather than "
            "informatively -- reported as such instead of being presented as Condition B "
            "winning a precision contest."
        ) if (pa == 0.0) else None,
    }

    result = {
        "phase": 5,
        "scoring_population": len(skill_ids),
        "label_counts": {k: sum(1 for s in skill_ids if labels[s]["label"] == k)
                          for k in ("invalidated", "partial", "valid")},
        "bootstrap": {"n_resamples": N_BOOT, "seed": SEED, "method": "percentile (2.5/97.5)",
                       "resampling_unit": "skill"},
        "metric_definitions": {
            "invalidation_recall": "|flagged & invalidated| / |invalidated|",
            "invalidation_precision": "|flagged & invalidated| / |flagged|",
            "silent_wrong_action_rate": "|silent wrong actions| / |invalidated|",
            "primary_variant": "partial scored as a separate class, NOT folded into "
                                "invalidated (fixed in preregistration section 5)",
            "secondary_variant": "partial_inclusive -- reported alongside, never instead",
        },
        "conditions": rows,
        "decision": decision,
    }

    with open(f"{OUT_DIR}/main_results.json", "w") as fh:
        json.dump(result, fh, indent=2)

    with open(f"{OUT_DIR}/main_results.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["condition", "variant", "invalidation_recall", "recall_ci",
                     "invalidation_precision", "precision_ci",
                     "silent_wrong_action_rate", "swa_ci",
                     "n_flagged", "n_true_positive", "n_positive_class"])
        for r in rows:
            for variant in ("primary", "partial_inclusive"):
                m = r[variant]
                w.writerow([
                    r["condition"], variant,
                    fmt(m["point"]["recall"]), fmt_ci(m, "recall"),
                    fmt(m["point"]["precision"]), fmt_ci(m, "precision"),
                    fmt(m["point"]["silent_wrong_action_rate"]),
                    fmt_ci(m, "silent_wrong_action_rate"),
                    m["counts"]["n_flagged"], m["counts"]["n_true_positive"],
                    m["counts"]["n_positive"],
                ])

    # human-readable main table
    lines = ["# Phase 5 Main Results", "",
             f"Population: {len(skill_ids)} skills "
             f"({result['label_counts']['invalidated']} invalidated, "
             f"{result['label_counts']['partial']} partial, "
             f"{result['label_counts']['valid']} valid). "
             f"Bootstrap: {N_BOOT} resamples over skills, seed {SEED}, percentile CIs.", "",
             "## Primary (partial scored as a separate class)", "",
             "| Condition | Invalidation recall | Invalidation precision | Silent wrong action rate |",
             "|---|---|---|---|"]
    for r in rows:
        m = r["primary"]
        lines.append(
            f"| {r['condition']} | {fmt(m['point']['recall'])} {fmt_ci(m,'recall')} "
            f"| {fmt(m['point']['precision'])} {fmt_ci(m,'precision')} "
            f"| {fmt(m['point']['silent_wrong_action_rate'])} "
            f"{fmt_ci(m,'silent_wrong_action_rate')} |")
    lines += ["", "## Secondary (partial folded into the positive class)", "",
              "| Condition | Recall | Precision | Silent wrong action rate |",
              "|---|---|---|---|"]
    for r in rows:
        m = r["partial_inclusive"]
        lines.append(
            f"| {r['condition']} | {fmt(m['point']['recall'])} {fmt_ci(m,'recall')} "
            f"| {fmt(m['point']['precision'])} {fmt_ci(m,'precision')} "
            f"| {fmt(m['point']['silent_wrong_action_rate'])} "
            f"{fmt_ci(m,'silent_wrong_action_rate')} |")
    lines += ["", "## Preregistered decision", "",
              f"- recall(B) = {fmt(rb)} vs recall(A) = {fmt(ra)} -> improved: {recall_improved}",
              f"- precision drop (A - B) = {precision_drop_pts:.1f} pts "
              f"(bound: 5.0) -> within bound: {precision_within_bound}",
              f"- **Verdict: {verdict}** -- {why}", ""]
    with open(f"{OUT_DIR}/main_results.md", "w") as fh:
        fh.write("\n".join(lines) + "\n")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
