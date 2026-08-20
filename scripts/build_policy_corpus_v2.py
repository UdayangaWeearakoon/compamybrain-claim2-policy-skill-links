#!/usr/bin/env python3
"""
Claim 2 -- Phase 3, step B: build the v2 policy corpus.

Consumes ground_truth/_supersession_plan.json (from select_supersessions.py)
plus a hand-authored REAL_REWRITES map giving the actual v2 text for each
selected rule -- the plan only decided WHICH rules to supersede and
whether they're "hard" or "value_dependent"; the concrete new wording, the
substantive design decision that must actually change the tested
behavior, is written here.

Three kinds of policy get a v2 document:
  1. Real-supersession policies (18, from the plan): exactly the rule(s)
     the plan selected are rewritten with real behavioral content. Every
     OTHER rule in that same document is either left byte-identical, or
     -- for one rule per policy -- given a cosmetic-only reword (see
     COSMETIC_TARGET below), so the v2 document itself is a realistic mix
     of "real change" and "textual noise", exactly what the execution
     guide's distractor requirement describes ("alongside real
     supersessions, inject cosmetic edits").
  2. Cosmetic-only policies (5, COSMETIC_ONLY_POLICIES below, chosen from
     the policies the plan never touched): every rule keeps its exact v1
     testable content; only wording/order changes. No rule_id from these
     policies is ever added to a "superseded" set, so every skill under
     them stays Valid by construction -- a whole-document distractor.
  3. Untouched policies: no v2 at all, still v1.

Cosmetic edits (both kinds) use ONLY a fixed, meaning-preserving synonym
substitution (SYNONYM_MAP, filler/connector words only) plus reordering
the rules array -- never touching a number, tier name, action-button
name, or object noun -- so "cosmetic" is a structural guarantee, not a
claim to take on faith. verify_cosmetic() checks this mechanically before
any v2 file is written.
"""
import json
import os
import re
import glob

V1_DIR = "policy_corpus/v1"
V2_DIR = "policy_corpus/v2"
PLAN_PATH = "ground_truth/_supersession_plan.json"
os.makedirs(V2_DIR, exist_ok=True)

EFFECTIVE_V2 = "2026-01-15T00:00:00Z"

# ---------------------------------------------------------------------
# Real rewrites: policy_id -> rule_id -> new statement text. One entry for
# every action in the plan. Each change note documents old -> new and why
# it's a genuine behavioral flip, not a rewording.
# ---------------------------------------------------------------------
REAL_REWRITES = {
    ("POL-004", "POL-004-R3"): (
        "Guest members are never eligible for a return, receipt or no "
        "receipt, regardless of how long ago the purchase was made.",
        "Tightens guest eligibility from conditional (denied only past the "
        "30-day window without a receipt) to an unconditional denial -- any "
        "guest return skill that still checks the window/receipt is now wrong."
    ),
    ("POL-004", "POL-004-R2"): (
        "Return eligibility is gated by membership level: Gold members "
        "receive unlimited returns; Silver members are eligible within 3 "
        "months of purchase, or with a receipt, or if the item is in "
        "original packaging; Bronze members are eligible within 60 days, "
        "or with a receipt, or in original packaging; Guest members are "
        "eligible within 30 days, or with a receipt.",
        "Tightens the Silver window 6mo->3mo and Bronze window 90->60 days. "
        "Whether a given historical case is now wrong depends on the actual "
        "purchase-to-request gap in that case, so this is value-dependent, "
        "not a blanket flip."
    ),
    ("POL-035", "POL-035-R3"): (
        "Bronze and Guest members are always denied the disputed refund "
        "amount; Ask the Oracle is no longer consulted for these tiers.",
        "Removes the Oracle check entirely for Bronze/Guest -- any skill "
        "whose action sequence still queries the Oracle for these tiers is "
        "now following a step the policy no longer permits."
    ),
    ("POL-035", "POL-035-R2"): (
        "Refund eligibility is gated by membership level: Gold members "
        "always receive the disputed amount; Silver members receive a "
        "refund only if the disputed amount is less than $25; Bronze and "
        "Guest members are evaluated via Ask the Oracle.",
        "Raises the Silver auto-refund ceiling $10->$25. Whether a given "
        "Silver case flips depends on the actual disputed amount, so "
        "value-dependent."
    ),
    ("POL-005", "POL-005-R1"): (
        "Before adjudicating a mystery fee, the agent must verify identity "
        "using full name, account ID, order ID, and phone number via "
        "Verify Identity.",
        "Adds a 4th required identity field (phone number). Every skill's "
        "recorded Verify Identity call used exactly 3 values, so it no "
        "longer satisfies the precondition -- a blanket flip, not "
        "value-dependent."
    ),
    ("POL-009", "POL-009-R1"): (
        "Before processing a shipping upgrade or downgrade, the agent must "
        "verify identity using full name, account ID, order ID, and phone "
        "number via Verify Identity.",
        "Same 4th-field verification hardening as POL-005-R1."
    ),
    ("POL-010", "POL-010-R1"): (
        "Before adding an item to an order, the agent must verify identity "
        "using full name, account ID, order ID, and phone number via "
        "Verify Identity.",
        "Same verification hardening."
    ),
    ("POL-011", "POL-011-R1"): (
        "Before cancelling or returning an order, the agent must verify "
        "identity using full name, account ID, order ID, and phone number "
        "via Verify Identity.",
        "Same verification hardening."
    ),
    ("POL-001", "POL-001-R1"): (
        "Before offering a refund, the agent must validate the purchase "
        "using the customer's username, email address, order ID, and "
        "phone number via Validate Purchase.",
        "Adds a 4th required field to Validate Purchase. Every skill's "
        "recorded call used exactly 3 values -- blanket flip."
    ),
    ("POL-002", "POL-002-R1"): (
        "Before modifying an existing refund, the agent must validate the "
        "purchase using the customer's username, email address, order ID, "
        "and phone number via Validate Purchase.",
        "Same Validate Purchase hardening."
    ),
    ("POL-003", "POL-003-R1"): (
        "Before reporting refund status, the agent must gather username, "
        "email address, order ID, and phone number, in that order, and "
        "validate via Validate Purchase.",
        "Same Validate Purchase hardening (plus the 4th field enters the "
        "required order)."
    ),
    ("POL-006", "POL-006-R1"): (
        "Before reporting delivery status, the agent must verify identity "
        "using full name, account ID, order ID, and phone number via "
        "Verify Identity.",
        "Same verification hardening."
    ),
    ("POL-007", "POL-007-R1"): (
        "Before changing a payment method, the agent must verify identity "
        "using full name, account ID, order ID, and phone number via "
        "Verify Identity.",
        "Same verification hardening."
    ),
    ("POL-008", "POL-008-R1"): (
        "Before resolving a quantity discrepancy, the agent must verify "
        "identity using full name, account ID, order ID, and phone number "
        "via Verify Identity.",
        "Same verification hardening."
    ),
    ("POL-012", "POL-012-R1"): (
        "To recover a username, the agent must collect all 4 of the "
        "following identity items: full name, zip code, phone number, and "
        "email address, via Verify Identity.",
        "Raises the requirement from 3-of-4 to 4-of-4. Recorded skill "
        "traces collected only 3 items -- blanket flip."
    ),
    ("POL-025", "POL-025-R1"): (
        "A promo code dispute is classified as 'out of date' if the code "
        "was issued more than 14 days ago, and 'invalid' otherwise; both "
        "classifications follow the same resolution procedure.",
        "Doubles the out-of-date threshold 7->14 days. Value-dependent on "
        "the actual code age in each case."
    ),
    ("POL-034", "POL-034-R2"): (
        "Extension eligibility is gated strictly by membership level: Gold "
        "members always qualify; Silver members qualify only if the "
        "payment is no more than 3 days late; Bronze and Guest members "
        "never qualify.",
        "Loosens the Silver late-payment allowance 1->3 days. "
        "Value-dependent on the actual lateness in each case."
    ),
    ("POL-017", "POL-017-R3"): (
        "If the Oracle confirms the error, the extra service must be "
        "removed via Update Account, and the agent must offer a refund of "
        "$60 as the standard erroneous-service-charge amount.",
        "Raises the standard refund amount $40->$60. Value-dependent: only "
        "wrong for skills whose recorded refund value reflects the old "
        "standard amount."
    ),
    ("POL-020", "POL-020-R3"): (
        "If the Oracle confirms the credit is missing, the agent must add "
        "the amount requested by the customer, or a standard amount of $60 "
        "if the customer does not know, and issue it via Promo Code.",
        "Raises the standard missing-credit amount $40->$60. "
        "Value-dependent."
    ),
    ("POL-030", "POL-030-R3"): (
        "A replacement order (new shipment) via Update Order and Make "
        "Purchase may only be initiated if the customer has been waiting "
        "10 days or longer; waits under 10 days do not qualify for a "
        "replacement shipment.",
        "Raises the wait threshold 7->10 days. Value-dependent on the "
        "actual wait in each case."
    ),
}

# One additional rule per real-supersession policy gets a cosmetic-only
# reword (never the rule that was just superseded) -- an in-document
# distractor. Picked deterministically: the first rule in the policy's v1
# rule list that is NOT the superseded rule(s).
SYNONYM_MAP = [
    (r"\bmust\b", "is required to"),
    (r"\bbefore\b", "prior to"),
    (r"\bmay\b", "is permitted to"),
    (r"\bif\b", "in the event that"),
]


def apply_cosmetic_reword(statement):
    out = statement
    for pattern, repl in SYNONYM_MAP:
        out = re.sub(pattern, repl, out, count=1)
    return out


def verify_cosmetic(old, new):
    """Mechanically confirm a reword touched only whitelisted connector
    words: strip the substituted phrases back out of both strings (via the
    same substitution table, in reverse) and require the residues match
    -- guarantees no number, tier name, or action name changed."""
    def normalize(s):
        s2 = s
        for pattern, repl in SYNONYM_MAP:
            s2 = re.sub(repl, "<SYN>", s2)
            s2 = re.sub(pattern, "<SYN>", s2)
        return s2
    return normalize(old) == normalize(new) or old == new


# Whole-document-only cosmetic (distractor) policies: chosen from policies
# NOT selected by select_supersessions.py, in POL-ID order, first 5.
COSMETIC_ONLY_COUNT = 5


def load_plan():
    return json.load(open(PLAN_PATH))


def load_v1_policies():
    out = {}
    for f in sorted(glob.glob(f"{V1_DIR}/POL-*.json")):
        d = json.load(open(f))
        out[d["policy_id"]] = d
    return out


def pick_cosmetic_only_policies(v1_policies, real_pids):
    remaining = [pid for pid in sorted(v1_policies.keys()) if pid not in real_pids]
    return remaining[:COSMETIC_ONLY_COUNT]


def build_real_v2(policy, superseded_rule_ids):
    pid = policy["policy_id"]
    rules_v1 = policy["rules"]
    cosmetic_target = None
    for r in rules_v1:
        if r["rule_id"] not in superseded_rule_ids:
            cosmetic_target = r["rule_id"]
            break

    new_rules = []
    change_log = []
    for r in rules_v1:
        rid = r["rule_id"]
        if rid in superseded_rule_ids:
            new_text, note = REAL_REWRITES[(pid, rid)]
            new_rules.append({"rule_id": rid, "statement": new_text})
            change_log.append({"rule_id": rid, "change_type": "real_supersession",
                                 "v1_statement": r["statement"], "v2_statement": new_text,
                                 "note": note})
        elif rid == cosmetic_target:
            new_text = apply_cosmetic_reword(r["statement"])
            assert verify_cosmetic(r["statement"], new_text), f"cosmetic check failed for {rid}"
            new_rules.append({"rule_id": rid, "statement": new_text})
            change_log.append({"rule_id": rid, "change_type": "cosmetic_reword",
                                 "v1_statement": r["statement"], "v2_statement": new_text,
                                 "note": "Distractor: connector-word reword only, no testable content changed."})
        else:
            new_rules.append({"rule_id": rid, "statement": r["statement"]})
            change_log.append({"rule_id": rid, "change_type": "unchanged",
                                 "v1_statement": r["statement"], "v2_statement": r["statement"]})

    # Reorder the rules array (cosmetic, document-level) -- reverse order.
    new_rules_reordered = list(reversed(new_rules))

    v2 = dict(policy)
    v2["version"] = "v2"
    v2["effective_timestamp"] = EFFECTIVE_V2
    v2["supersedes"] = "v1"
    v2["rules"] = new_rules_reordered
    v2["_change_log"] = change_log
    v2["_change_summary"] = "real_supersession"
    return v2


def build_cosmetic_only_v2(policy):
    pid = policy["policy_id"]
    new_rules = []
    change_log = []
    for r in policy["rules"]:
        new_text = apply_cosmetic_reword(r["statement"])
        assert verify_cosmetic(r["statement"], new_text), f"cosmetic check failed for {r['rule_id']}"
        new_rules.append({"rule_id": r["rule_id"], "statement": new_text})
        change_log.append({"rule_id": r["rule_id"], "change_type": "cosmetic_reword",
                             "v1_statement": r["statement"], "v2_statement": new_text,
                             "note": "Whole-document distractor: connector-word reword only."})
    new_rules_reordered = list(reversed(new_rules))

    v2 = dict(policy)
    v2["version"] = "v2"
    v2["effective_timestamp"] = EFFECTIVE_V2
    v2["supersedes"] = "v1"
    v2["rules"] = new_rules_reordered
    v2["_change_log"] = change_log
    v2["_change_summary"] = "cosmetic_only"
    return v2


def main():
    plan = load_plan()
    v1_policies = load_v1_policies()
    real_pids = plan["real_supersession_policies"]

    # group plan actions by policy
    by_policy = {}
    for a in plan["actions"]:
        by_policy.setdefault(a["policy_id"], []).append(a["rule_id"])

    cosmetic_only_pids = pick_cosmetic_only_policies(v1_policies, set(real_pids))

    written = []
    for pid in real_pids:
        superseded = set(by_policy[pid])
        for rid in superseded:
            assert (pid, rid) in REAL_REWRITES, f"missing REAL_REWRITES entry for {pid} {rid}"
        v2 = build_real_v2(v1_policies[pid], superseded)
        path = f"{V2_DIR}/{pid}_v2.json"
        with open(path, "w") as fh:
            json.dump(v2, fh, indent=2)
        written.append((pid, "real_supersession", len(superseded)))

    for pid in cosmetic_only_pids:
        v2 = build_cosmetic_only_v2(v1_policies[pid])
        path = f"{V2_DIR}/{pid}_v2.json"
        with open(path, "w") as fh:
            json.dump(v2, fh, indent=2)
        written.append((pid, "cosmetic_only", 0))

    untouched = [pid for pid in sorted(v1_policies.keys())
                  if pid not in real_pids and pid not in cosmetic_only_pids]

    index = {
        "total_policies": len(v1_policies),
        "real_supersession_policies": real_pids,
        "cosmetic_only_policies": cosmetic_only_pids,
        "untouched_policies": untouched,
        "v2_document_count": len(written),
        "v2_share_of_total": round(len(written) / len(v1_policies), 3),
    }
    with open(f"{V2_DIR}/_v2_index.json", "w") as fh:
        json.dump(index, fh, indent=2)

    print(f"Wrote {len(written)} v2 policy documents ({len(real_pids)} real-supersession, "
          f"{len(cosmetic_only_pids)} cosmetic-only) out of {len(v1_policies)} total policies "
          f"({len(written)/len(v1_policies)*100:.1f}% got a v2).")
    print(f"Untouched (v1 only): {len(untouched)}")


if __name__ == "__main__":
    main()
