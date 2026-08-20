#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step A: select which v1 rules to supersede in v2, and
which policies get cosmetic-only (distractor) v2 edits, to hit the
execution guide's class-balance target (~40% invalidated / 20% partial /
40% valid across the skill library) while respecting the 30-50%-of-
policies-get-a-v2 band.

Deterministic, no randomness. Rules are classified from their v1 text
(numeric-threshold present -> "value_dependent"; otherwise -> "hard").
Impact sets are computed from the REAL skill_library/v1 rule_ids, not
re-derived from text.

Design, found by inspecting the impact numbers directly: most
non-tier-gated policies' skills all share the identical full rule set, so
a single "hard" rule superseded there invalidates every skill under that
policy at once, leaving no room in that same policy for a "partial"
skill (hard always wins the per-skill label). But several tier-gated
policies have a hard rule scoped to only SOME branches and a numeric
("value_dependent") rule that reaches ALL branches -- superseding both at
once splits that one policy cleanly: the hard-scoped branches become
Invalidated, the remaining branches (touched only by the value rule)
become Partial. This "both" mode is strictly more efficient (2 labels
from 1 policy) than spending 2 separate policies, so it's tried first,
which is what keeps the real-supersession policy count inside the 30-50%
band instead of needing one policy per few skills.

For every policy, up to 4 modes are computed:
  - "both":       best hard rule + best value rule together (only when
                   their impact sets aren't identical, i.e. a split exists)
  - "hard_only":  best hard rule alone -> whole policy Invalidated
  - "value_only": best value rule alone -> whole policy Partial
  - "none":       untouched (Valid), a later candidate for a cosmetic v2
Policies are greedily assigned the mode that best reduces the current
(invalidated, partial) deficit, preferring "both", in descending order of
total skills reachable -- so the target is met with the fewest policies.

Label logic this plan is designed for (applied later by label_ground_truth.py):
  - a skill's superseded-rule intersection is empty            -> Valid
  - intersection contains >=1 "hard"-superseded rule           -> Invalidated
  - intersection is non-empty and entirely "value_dependent"   -> Partially invalidated
"""
import json
import re
import glob
from collections import defaultdict

POLICY_DIR = "policy_corpus/v1"
SKILL_DIR = "skill_library/v1"

NUM_PAT = re.compile(r"\$\d+|\b\d+\s*(?:dollars?|percent|%|days?|hours?)\b", re.I)

TARGET_INVALIDATED = 52
TARGET_PARTIAL = 26
TOLERANCE = 2
# Real per-policy skill density (25 policies w/ 3 skills, 8 w/ 4, 4 w/ 2 --
# from skill_library/v1) makes TARGET_INVALIDATED+TARGET_PARTIAL=78 skills
# unreachable within the guide's 30-50%-of-policies band: even spending
# every one of the 18 largest policies (48.6% of 37) on a single bucket
# each caps total reachable skills at 62. MAX_POLICIES enforces the guide's
# upper bound; the achieved class split is reported as whatever the greedy
# fill reaches within it (documented explicitly, see ground_truth/CONSTRUCTION.md).
MAX_POLICIES = 18


def load():
    policies = {}
    for f in sorted(glob.glob(f"{POLICY_DIR}/POL-*.json")):
        d = json.load(open(f))
        policies[d["policy_id"]] = d
    skills = {}
    for f in sorted(glob.glob(f"{SKILL_DIR}/SK-*.json")):
        d = json.load(open(f))
        skills[d["skill_id"]] = d
    linked = {sid: s for sid, s in skills.items() if not s["is_negative_control"]}
    return policies, linked


def rules_by_policy(policies, linked):
    by_policy_skills = defaultdict(list)
    for sid, s in linked.items():
        by_policy_skills[s["policy_id"]].append(sid)

    out = {}
    for pid in sorted(policies.keys()):
        p = policies[pid]
        hard, value = [], []
        for r in p["rules"]:
            rid = r["rule_id"]
            impacted = [sid for sid in by_policy_skills[pid] if rid in linked[sid]["rule_ids"]]
            if not impacted:
                continue
            entry = {"policy_id": pid, "rule_id": rid, "statement": r["statement"],
                       "impacted": impacted}
            if NUM_PAT.search(r["statement"]):
                entry["type"] = "value_dependent"
                value.append(entry)
            else:
                entry["type"] = "hard"
                hard.append(entry)
        out[pid] = {"hard": hard, "value": value}
    return out


def policy_modes(pid, rules):
    """Compute the available modes for one policy: {mode_name: (actions, inv_set, part_set)}."""
    modes = {}
    best_hard = max(rules["hard"], key=lambda c: len(c["impacted"])) if rules["hard"] else None
    best_value = max(rules["value"], key=lambda c: len(c["impacted"])) if rules["value"] else None

    if best_hard:
        inv = set(best_hard["impacted"])
        modes["hard_only"] = ([best_hard], inv, set())
    if best_value:
        part = set(best_value["impacted"])
        modes["value_only"] = ([best_value], set(), part)

    # "both": try every hard candidate (not just the widest) paired with the
    # widest value candidate, and keep whichever pairing maximizes total
    # skills labeled (inv+part). A narrow, tier-scoped hard rule (e.g. a
    # single branch's denial clause) leaves the rest of the value rule's
    # reach as Partial instead of being swallowed whole by a universal hard
    # pick -- that's the split this mode exists to find.
    if best_value:
        best_split = None
        for hard_cand in rules["hard"]:
            inv = set(hard_cand["impacted"])
            part = set(best_value["impacted"]) - inv
            if not part:
                continue
            total = len(inv) + len(part)
            if best_split is None or total > best_split[0]:
                best_split = (total, hard_cand, inv, part)
        if best_split:
            _, hard_cand, inv, part = best_split
            modes["both"] = ([hard_cand, best_value], inv, part)
    return modes


def main():
    policies, linked = load()
    rules = rules_by_policy(policies, linked)

    all_modes = {pid: policy_modes(pid, rules[pid]) for pid in policies}

    # Iterative greedy, capped at MAX_POLICIES. At each step, pick whichever
    # bucket (invalidated vs partial) is proportionally further from ITS
    # share of the original 52:26 (2:1) target ratio -- not raw remaining
    # count, which would starve "partial" every time since 26 < 52 in
    # absolute terms even when partial is proportionally further behind --
    # then take the single best not-yet-used policy for that bucket ("both"
    # mode preferred whenever it's on offer, since it serves both buckets
    # from one policy). Repeats until MAX_POLICIES is spent or both targets
    # are met (whichever first).
    inv_have, part_have = 0, 0
    chosen_actions = []
    used_pids = set()

    def proportional_deficit():
        return (TARGET_INVALIDATED - inv_have) / TARGET_INVALIDATED, \
               (TARGET_PARTIAL - part_have) / TARGET_PARTIAL

    while len(used_pids) < MAX_POLICIES:
        inv_def, part_def = proportional_deficit()
        if inv_def <= 0 and part_def <= 0:
            break
        prefer_inv = inv_def >= part_def

        # Look for a "both" mode pick first -- always worth it if available,
        # since it advances both buckets from a single policy slot.
        both_pick = None
        for pid, modes in all_modes.items():
            if pid in used_pids or "both" not in modes:
                continue
            actions, inv_set, part_set = modes["both"]
            if not inv_set and not part_set:
                continue
            both_pick = (pid, actions, inv_set, part_set)
            break  # policies dict is already POL-ID ordered; first hit is fine, deterministic
        if both_pick:
            pid, actions, inv_set, part_set = both_pick
            chosen_actions.extend(actions)
            inv_have += len(inv_set)
            part_have += len(part_set)
            used_pids.add(pid)
            continue

        # Otherwise take the largest single-mode candidate for whichever
        # bucket is proportionally more behind.
        wanted_mode = "hard_only" if prefer_inv else "value_only"
        best = None
        for pid, modes in all_modes.items():
            if pid in used_pids or wanted_mode not in modes:
                continue
            actions, inv_set, part_set = modes[wanted_mode]
            size = len(inv_set) + len(part_set)
            if best is None or size > best[0]:
                best = (size, pid, actions, inv_set, part_set)
        if best is None:
            # no more candidates for the preferred bucket -- try the other
            wanted_mode = "value_only" if prefer_inv else "hard_only"
            for pid, modes in all_modes.items():
                if pid in used_pids or wanted_mode not in modes:
                    continue
                actions, inv_set, part_set = modes[wanted_mode]
                size = len(inv_set) + len(part_set)
                if best is None or size > best[0]:
                    best = (size, pid, actions, inv_set, part_set)
        if best is None:
            break  # genuinely nothing left to add
        _, pid, actions, inv_set, part_set = best
        chosen_actions.extend(actions)
        inv_have += len(inv_set)
        part_have += len(part_set)
        used_pids.add(pid)

    print(f"Total policies: {len(policies)}")
    print(f"Real-supersession policies: {len(used_pids)} ({len(used_pids)/len(policies)*100:.1f}%)")
    print(f"Rule-level supersession actions: {len(chosen_actions)}")
    print(f"Achieved: invalidated={inv_have}, partial={part_have}, "
          f"valid={len(linked)-inv_have-part_have}")
    print(f"Targets:  invalidated={TARGET_INVALIDATED}, partial={TARGET_PARTIAL}, "
          f"valid={len(linked)-TARGET_INVALIDATED-TARGET_PARTIAL}")
    print(f"Used policies: {sorted(used_pids)}")

    plan = {
        "target": {"invalidated": TARGET_INVALIDATED, "partial": TARGET_PARTIAL,
                    "valid": len(linked) - TARGET_INVALIDATED - TARGET_PARTIAL},
        "achieved_counts": {"invalidated": inv_have, "partial": part_have,
                              "valid": len(linked) - inv_have - part_have},
        "real_supersession_policies": sorted(used_pids),
        "actions": [{"policy_id": c["policy_id"], "rule_id": c["rule_id"],
                      "type": c["type"], "statement": c["statement"],
                      "impacted_skill_ids": c["impacted"]} for c in chosen_actions],
    }
    with open("ground_truth/_supersession_plan.json", "w") as fh:
        json.dump(plan, fh, indent=2)
    print("\nWrote ground_truth/_supersession_plan.json")


if __name__ == "__main__":
    main()
