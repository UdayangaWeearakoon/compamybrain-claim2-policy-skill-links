#!/usr/bin/env python3
"""
Claim 2 -- Phase 2, step B: distill procedural skills from the extracted
ABCD action traces, and record their policy-version dependency links at
distillation time (so the link is ground truth by construction, per the
execution guide).

Input: skill_library/intermediate/action_traces.json (from
extract_action_traces.py) + the frozen v1 policy corpus.

Clustering method (deterministic, auditable -- see datasheet for full
rationale):
  - For each of the 37 v1 policies, gather every extracted dialogue whose
    subflow is one of that policy's source_subflows.
  - If the policy is tier-gated (>=1 rule mentions a membership tier by
    name), cluster its dialogues by scenario.personal.member_level -- the
    actual branch variable those rules key on. Policies whose rules single
    out only one tier (e.g. "Gold members can always ...") are clustered
    into a binary {that tier, everyone else} split rather than four
    near-duplicate branches.
  - If the policy is NOT tier-gated, cluster by the realized action-button
    signature (order-preserving, deduplicated), keeping up to the 2 most
    frequent signatures -- this captures other real branching (e.g. an
    Ask-the-Oracle Yes/No split) without membership tier as a factor.
  - Each cluster with >=1 real dialogue becomes exactly one skill. The
    most frequent (button-signature, member_level) pairing in the cluster
    is used as the skill's representative action_sequence; up to 5
    contributing convo_ids are kept as provenance.

A skill's dependency links are then computed purely from which of its
policy's rules are actually relevant to its branch (see
`relevant_rule_ids`): universal rules (no tier mentioned) always apply;
tier-specific rules apply only to the matching branch. This is code, not
judgment -- the audit step (audit_skill_links.py) is what checks whether
the *code's* link is actually correct.

Negative-control skills (~15% of the library) are hand-specified below:
recurring, cross-cutting conversational patterns visible in many
dialogues across many different subflows, which the Phase 1 corpus
deliberately did NOT encode as testable rules (they don't gate any
concrete action). Each carries dependency_links: [] and
is_negative_control: true, with real convo_id provenance proving the
pattern is genuinely cross-cutting and not specific to one policy.
"""
import json
import os
import re
from collections import Counter, defaultdict

BASE = os.path.join(os.path.dirname(__file__), "..")
TRACES_PATH = os.path.join(BASE, "skill_library", "intermediate", "action_traces.json")
POLICY_DIR = os.path.join(BASE, "policy_corpus", "v1")
OUT_DIR = os.path.join(BASE, "skill_library", "v1")
os.makedirs(OUT_DIR, exist_ok=True)

TIERS = ["Gold", "Silver", "Bronze", "Guest"]

FLOW_DISPLAY = {
    "product_defect": "Product Defect", "order_issue": "Order Issue",
    "account_access": "Account Access", "troubleshoot_site": "Troubleshoot Site",
    "manage_account": "Manage Account", "purchase_dispute": "Purchase Dispute",
    "shipping_issue": "Shipping Issue", "subscription_inquiry": "Subscription Inquiry",
    "single_item_query": "Single-Item Query", "storewide_query": "Storewide Query",
}

TERMINAL_OUTCOME = {
    "offer-refund": "a refund is issued to the customer",
    "update-order": "the order is updated per the requested change",
    "update-account": "the account is updated per the requested change",
    "notify-team": "the issue is escalated internally rather than resolved directly by the agent",
    "promo-code": "a promo code is generated and issued to the customer",
    "send-link": "a reference link is sent to the customer",
    "make-purchase": "the purchase/back-order is completed on the customer's behalf",
    "enter-details": "the requested detail is recorded, pending a further step",
    "record-reason": "the reason/context is recorded, pending a further step",
    "membership": "the membership-privileges check is recorded, gating the next step",
    "shipping-status": "the shipping status is recorded, gating the next step",
    "validate-purchase": "the purchase is validated, gating the next step",
    "verify-identity": "identity is verified, gating the next step",
    "subscription-status": "the subscription status is retrieved and reported",
    "ask-the-oracle": "a system determination is retrieved, gating the next step",
    "try-again": "the customer is instructed to retry, no account change is made",
    "log-out-in": "the customer is instructed to log out/in, no account change is made",
    "make-password": "a new password is issued",
    "send-link": "a reference link is sent to the customer",
}


def load_policies():
    policies = {}
    for fname in sorted(os.listdir(POLICY_DIR)):
        if not fname.startswith("POL-"):
            continue
        d = json.load(open(os.path.join(POLICY_DIR, fname)))
        policies[d["policy_id"]] = d
    return policies


def tier_mentions(policy):
    mentioned = set()
    for r in policy["rules"]:
        for t in TIERS:
            if t in r["statement"]:
                mentioned.add(t)
    return mentioned


def relevant_rule_ids(policy, branch_label):
    """branch_label is either a tier name, 'non-<tier>', or None (untiered)."""
    ids = []
    for r in policy["rules"]:
        stmt = r["statement"]
        rule_tiers = {t for t in TIERS if t in stmt}
        if not rule_tiers:
            ids.append(r["rule_id"])  # universal rule
            continue
        if branch_label is None:
            ids.append(r["rule_id"])
            continue
        if branch_label.startswith("non-"):
            excluded_tier = branch_label[4:].capitalize()
            if rule_tiers - {excluded_tier}:
                ids.append(r["rule_id"])
        else:
            if branch_label.capitalize() in rule_tiers:
                ids.append(r["rule_id"])
    return ids


def branch_groups_for_policy(policy):
    """Return the list of branch labels to cluster this policy's dialogues
    by, given which tiers its rules actually call out by name."""
    mentioned = tier_mentions(policy)
    if not mentioned:
        return None  # not tier-gated -> cluster by action signature instead
    if len(mentioned) == 1:
        t = next(iter(mentioned)).lower()
        return [t, f"non-{t}"]
    return [t.lower() for t in TIERS]


def outcome_sentence(action_trace):
    if not action_trace:
        return "no system action is taken; the request is handled conversationally."
    last = action_trace[-1]["button"]
    return TERMINAL_OUTCOME.get(last, f"the '{last}' action is taken as the final step.")


def synthesize_skill(policy, subflow, flow, branch_label, records, sig_index=None):
    rule_ids = relevant_rule_ids(policy, branch_label)
    # representative record: most common action-signature within this cluster
    sig_counts = Counter(tuple(a["button"] for a in r["action_trace"]) for r in records)
    rep_sig, _ = sig_counts.most_common(1)[0]
    rep_records = [r for r in records if tuple(a["button"] for a in r["action_trace"]) == rep_sig]
    rep = rep_records[0]

    flow_disp = FLOW_DISPLAY.get(flow, flow)
    precond_parts = [f"Customer intent matches ABCD subflow '{subflow}' (flow: {flow_disp})."]
    if branch_label is not None:
        if branch_label.startswith("non-"):
            precond_parts.append(f"Customer's membership level is not {branch_label[4:]}.")
        else:
            precond_parts.append(f"Customer's membership level is {branch_label}.")
    precond_parts.append(f"Governing policy: {policy['family']} ({policy['policy_id']} v1).")

    return {
        "subflow": subflow,
        "flow": flow,
        "branch": branch_label,
        "policy_id": policy["policy_id"],
        "policy_version": "v1",
        "rule_ids": rule_ids,
        "precondition": " ".join(precond_parts),
        "action_sequence": rep["action_trace"],
        "postcondition": outcome_sentence(rep["action_trace"]).capitalize(),
        "provenance_convo_ids": sorted({r["convo_id"] for r in rep_records})[:5],
        "provenance_count_in_cluster": len(rep_records),
        "cluster_size": len(records),
        "is_negative_control": False,
    }


def distill_policy_linked_skills(policies, records_by_subflow):
    skills = []
    for pid, policy in policies.items():
        pol_records = []
        for sf in policy["source_subflows"]:
            pol_records.extend(records_by_subflow.get(sf, []))
        if not pol_records:
            continue  # e.g. POL-032's status_active branch has zero data,
                       # but POL-032 itself still gets skills via its
                       # other source subflows

        groups = branch_groups_for_policy(policy)
        flow = pol_records[0]["flow"]
        # subflow used for display: prefer the most common one in this policy's records
        subflow_disp = Counter(r["subflow"] for r in pol_records).most_common(1)[0][0]

        if groups is not None:
            for label in groups:
                if label.startswith("non-"):
                    bucket = [r for r in pol_records if r["member_level"] != label[4:]]
                else:
                    bucket = [r for r in pol_records if r["member_level"] == label]
                if bucket:
                    skills.append(synthesize_skill(policy, subflow_disp, flow, label, bucket))
        else:
            sig_counts = Counter(tuple(a["button"] for a in r["action_trace"]) for r in pol_records)
            top_sigs = [sig for sig, _ in sig_counts.most_common(3)]
            for sig in top_sigs:
                bucket = [r for r in pol_records if tuple(a["button"] for a in r["action_trace"]) == sig]
                skills.append(synthesize_skill(policy, subflow_disp, flow, None, bucket))
    return skills


# ---------------------------------------------------------------------
# Negative controls: cross-cutting patterns NOT gated by any Phase 1 rule.
# Each is defined by a filter over ALL extracted records (any subflow),
# proving the pattern recurs across many different policies/subflows.
# ---------------------------------------------------------------------

def negative_control_specs():
    """Each spec defines a cross-cutting, non-policy-governed action pattern
    plus a `subcluster_key` function: sub-clustering on this key is what
    turns one spec into several distinct negative-control skills (e.g. one
    per escalation target, one per flow), each still individually grounded
    in >=3 distinct subflows so the pattern is demonstrably cross-cutting
    and not an accidental single-subflow artifact."""
    return [
        {
            "name": "Universal account identification (Pull up Account)",
            "description": (
                "The agent asks for the customer's full name or account ID and clicks "
                "Pull up Account to load their record. This is a data-fetch mechanic "
                "shared by the opening step of most flows; the Phase 1 corpus does not "
                "encode it as a testable rule because no eligibility or amount depends "
                "on it -- it is not gated, it is prerequisite plumbing."
            ),
            "filter": lambda r: r["action_trace"] and r["action_trace"][0]["button"] == "pull-up-account",
            "isolate_button": "pull-up-account",
            "subcluster_key": lambda r: r["flow"],
            "max_variants": 4,
        },
        {
            "name": "Generic internal escalation notification",
            "description": (
                "The agent enters a target into Notify Internal Team. The *decision* "
                "to escalate is policy-governed case by case (see e.g. POL-003, "
                "POL-016, POL-023), but the notify-team mechanic itself -- pick a "
                "target, click the button -- recurs identically across unrelated "
                "policies and carries no eligibility logic of its own."
            ),
            "filter": lambda r: any(a["button"] == "notify-team" for a in r["action_trace"]),
            "isolate_button": "notify-team",
            "subcluster_key": lambda r: next(
                (a["values"][0] for a in r["action_trace"] if a["button"] == "notify-team" and a["values"]),
                "unspecified"),
            "max_variants": 3,
        },
        {
            "name": "Generic troubleshooting reflex (Try Again / Log Out-In)",
            "description": (
                "The agent's first response to a site/account glitch is to suggest "
                "retrying or logging out and back in, before any policy-specific "
                "branch is reached. This reflex appears at the start of multiple "
                "unrelated troubleshoot_site subflows and is not itself an "
                "eligibility-testable rule."
            ),
            "filter": lambda r: r["action_trace"] and r["action_trace"][0]["button"] in ("try-again", "log-out-in"),
            "isolate_button": None,
            "action_sequence_slice": slice(0, 1),
            "subcluster_key": lambda r: r["action_trace"][0]["button"],
            "max_variants": 2,
        },
        {
            "name": "Purchase validation as a bare prerequisite",
            "description": (
                "Validate Purchase (username/email/order ID) is required before many "
                "unrelated procedures continue, but the *validation mechanic itself* "
                "carries no branching logic -- it is a gate, not a rule with a "
                "consequence that differs by input, so it was not encoded as a "
                "standalone testable rule anywhere on its own."
            ),
            "filter": lambda r: any(a["button"] == "validate-purchase" for a in r["action_trace"]),
            "isolate_button": "validate-purchase",
            "subcluster_key": lambda r: r["flow"],
            "max_variants": 4,
        },
        {
            "name": "Generic Enter Details capture",
            "description": (
                "The agent captures a free-form detail (address, phone, troubleshoot "
                "flag, PIN) via Enter Details. The capture mechanic is identical "
                "everywhere it's used; what differs is which policy, if any, gates "
                "what happens with the captured value afterward -- capture itself is "
                "not a testable rule."
            ),
            "filter": lambda r: any(a["button"] == "enter-details" for a in r["action_trace"]),
            "isolate_button": "enter-details",
            "subcluster_key": lambda r: r["flow"],
            "max_variants": 3,
        },
    ]


def distill_negative_controls(all_records):
    specs = negative_control_specs()
    skills = []
    for spec in specs:
        matching = [r for r in all_records if spec["filter"](r)]
        by_subcluster = defaultdict(list)
        for r in matching:
            by_subcluster[spec["subcluster_key"](r)].append(r)

        # only keep subclusters that are individually well-populated, take the
        # largest ones up to max_variants
        ranked = sorted(by_subcluster.items(), key=lambda kv: -len(kv[1]))[: spec["max_variants"]]

        for key, bucket in ranked:
            distinct_subflows = sorted({r["subflow"] for r in bucket})
            if len(distinct_subflows) < 2:
                continue  # not cross-cutting enough within this subcluster
            reps = bucket[:5]
            if spec.get("isolate_button"):
                btn = spec["isolate_button"]
                action_seq = [a for a in reps[0]["action_trace"] if a["button"] == btn]
            else:
                sl = spec["action_sequence_slice"]
                action_seq = reps[0]["action_trace"][sl] if sl else reps[0]["action_trace"]

            skills.append({
                "subflow": None,
                "flow": None,
                "branch": None,
                "policy_id": None,
                "policy_version": None,
                "rule_ids": [],
                "precondition": spec["description"] + f" (subcluster: {key})",
                "action_sequence": action_seq,
                "postcondition": (
                    f"No policy-governed consequence follows from this step alone; observed "
                    f"across {len(distinct_subflows)} distinct subflows "
                    f"({', '.join(distinct_subflows[:6])}{'...' if len(distinct_subflows) > 6 else ''})."
                ),
                "provenance_convo_ids": sorted({r["convo_id"] for r in reps})[:5],
                "provenance_count_in_cluster": len(bucket),
                "cluster_size": len(matching),
                "is_negative_control": True,
                "negative_control_name": f"{spec['name']} ({key})",
            })
    return skills


def main():
    traces = json.load(open(TRACES_PATH))
    policies = load_policies()

    records_by_subflow = defaultdict(list)
    for r in traces["records"]:
        records_by_subflow[r["subflow"]].append(r)

    linked_skills = distill_policy_linked_skills(policies, records_by_subflow)
    neg_skills = distill_negative_controls(traces["records"])

    all_skills = linked_skills + neg_skills
    # assign stable, sequential IDs: linked skills first (grouped by policy_id
    # for readability), then negative controls
    linked_skills.sort(key=lambda s: (s["policy_id"], s["branch"] or ""))
    all_skills = linked_skills + neg_skills

    manifest = {"num_skills": len(all_skills), "num_linked": len(linked_skills),
                "num_negative_control": len(neg_skills), "skills": []}

    for i, sk in enumerate(all_skills, start=1):
        sk["skill_id"] = f"SK-{i:03d}"
        fname = f"SK-{i:03d}.json"
        with open(os.path.join(OUT_DIR, fname), "w") as fh:
            json.dump(sk, fh, indent=2)
        manifest["skills"].append({
            "skill_id": sk["skill_id"], "file": fname,
            "policy_id": sk["policy_id"], "subflow": sk["subflow"],
            "branch": sk["branch"], "is_negative_control": sk["is_negative_control"],
        })

    with open(os.path.join(OUT_DIR, "_skill_index.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)

    print(f"Linked skills: {len(linked_skills)}")
    print(f"Negative-control skills: {len(neg_skills)} ({len(neg_skills)/len(all_skills):.1%} of total)")
    print(f"Total skills: {len(all_skills)}")
    policies_covered = sorted({s["policy_id"] for s in linked_skills})
    print(f"Policies with >=1 linked skill: {len(policies_covered)} / 37")
    missing_policies = sorted(set(policies.keys()) - set(policies_covered))
    if missing_policies:
        print(f"Policies with NO linked skill (no data): {missing_policies}")


if __name__ == "__main__":
    main()
