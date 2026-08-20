#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step A: extract real gold action traces from ABCD dialogues.

Reads the ABCD train split (data/abcd_v1.1.json, gunzipped from
abcd_v1.1.json.gz) and, for every dialogue, pulls out:
  - convo_id
  - flow, subflow (scenario ground truth)
  - member_level (scenario.personal.member_level -- the branch-determining
    variable for every tier-gated Phase 1 policy)
  - action_trace: the ordered list of (button, values) pairs taken from
    every turn where speaker == "action" (i.e. targets[1] == "take_action"),
    which is ABCD's own gold-label action sequence for that dialogue --
    not inferred or hallucinated.

This is pure extraction (no LLM, no judgment calls) -- deterministic and
reproducible given the same abcd_v1.1.json.gz. Its output
(action_traces.json) is the empirical substrate that
distill_skills.py clusters into skill variants.

Also separates out dialogues whose scenario.subflow does not correspond
to any of the 55 subflows the frozen v1 policy corpus was built from
(status_questions, status_delivery_date -- see NOTE below) so that gap is
visible rather than silently dropped.
"""
import gzip
import json
import os
from collections import Counter, defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..")
ABCD_JSON_GZ = os.path.join(BASE, "abcd-master", "data", "abcd_v1.1.json.gz")
OUT_DIR = os.path.join(BASE, "skill_library", "intermediate")
os.makedirs(OUT_DIR, exist_ok=True)

# NOTE: discovered during Phase 2 extraction (not present in the Phase 1
# source material -- guidelines.json / kb.json / ontology.json -- and
# therefore NOT covered by any frozen v1 policy document). Dialogues
# carrying these scenario.subflow values are set aside, not distilled,
# and the gap is reported rather than silently dropped or used to expand
# the frozen Phase 1 corpus.
UNCOVERED_SUBFLOWS = {"status_questions", "status_delivery_date"}

# FAQ dialogues carry a fine-grained scenario.subflow (e.g. "boots_how_3")
# rather than the coarse subflow ontology.json groups under
# single_item_query / storewide_query ("boots"). Map by prefix.
FAQ_PREFIXES = {
    "boots": "single_item_query", "shirt": "single_item_query",
    "jeans": "single_item_query", "jacket": "single_item_query",
    "pricing": "storewide_query", "membership": "storewide_query",
    "timing": "storewide_query", "policy": "storewide_query",
}


def coarse_subflow(raw_subflow):
    """Map a raw scenario.subflow value to the subflow key the Phase 1
    corpus indexes on. FAQ dialogues need their fine-grained question id
    (e.g. boots_how_3) collapsed to the coarse product/topic (boots)."""
    for prefix in FAQ_PREFIXES:
        if raw_subflow.startswith(prefix):
            return prefix
    return raw_subflow


def main():
    with gzip.open(ABCD_JSON_GZ, "rt") as fh:
        data = json.load(fh)

    train = data["train"]
    records = []
    uncovered = []
    subflow_counts = Counter()
    member_level_counts = Counter()

    for convo in train:
        scenario = convo["scenario"]
        raw_subflow = scenario["subflow"]
        flow = scenario["flow"]
        member_level = scenario["personal"]["member_level"]

        action_trace = []
        for turn in convo["delexed"]:
            targets = turn["targets"]
            # targets = [intent, nextstep, action, value_filling, ranking]
            if targets[1] == "take_action" and targets[2]:
                action_trace.append({"button": targets[2], "values": targets[3]})

        rec = {
            "convo_id": convo["convo_id"],
            "flow": flow,
            "raw_subflow": raw_subflow,
            "subflow": coarse_subflow(raw_subflow),
            "member_level": member_level,
            "order": {
                "purchase_date": scenario.get("order", {}).get("purchase_date"),
                "packaging": scenario.get("order", {}).get("packaging"),
            },
            "action_trace": action_trace,
        }

        if raw_subflow in UNCOVERED_SUBFLOWS:
            uncovered.append(rec)
            continue

        records.append(rec)
        subflow_counts[rec["subflow"]] += 1
        member_level_counts[member_level] += 1

    out = {
        "source": "abcd-master/data/abcd_v1.1.json.gz, train split",
        "num_train_dialogues": len(train),
        "num_extracted_covered": len(records),
        "num_excluded_uncovered_subflow": len(uncovered),
        "excluded_subflow_breakdown": dict(Counter(r["raw_subflow"] for r in uncovered)),
        "distinct_subflows_covered": len(subflow_counts),
        "member_level_distribution": dict(member_level_counts),
        "records": records,
    }
    out_path = os.path.join(OUT_DIR, "action_traces.json")
    with open(out_path, "w") as fh:
        json.dump(out, fh, indent=2)

    print(f"Train dialogues: {len(train)}")
    print(f"Extracted (covered by v1 policy corpus): {len(records)}")
    print(f"Excluded (uncovered subflow): {len(uncovered)} -- {out['excluded_subflow_breakdown']}")
    print(f"Distinct subflows covered: {len(subflow_counts)} / 55 expected")
    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
