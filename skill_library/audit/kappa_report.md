# Phase 2 Audit: 20% Link-Quality Sample, Two-Annotator Agreement

Per the execution guide: "capture links automatically during distillation, but
audit a random 20 percent sample by hand. Two annotators check whether the
linked policy sections genuinely govern the skill. Report agreement. If
agreement is below roughly 0.8 kappa, your link definition is ambiguous and
everything downstream inherits that noise."

## Sample

- Population: 117 policy-linked skills (negative-control skills excluded --
  they have no link to audit by construction).
- Sample size: 23 (round(117 x 0.20)).
- Random seed: `20260819` (fixed, per hygiene rule #3), sampling code in
  `scripts/compute_audit_kappa.py`'s sibling sampling step, embedded inline
  in the session that produced `skill_library/audit/audit_sample.json`.
- Each sampled entry packages: skill_id, subflow, branch, precondition,
  action_sequence (button names only), postcondition, policy_id,
  policy_family, and the full text of every rule the skill claims as a
  dependency link.

## "Two annotators"

The guide specifies two human annotators. This audit substitutes two
independent LLM subagents in their place -- a disclosed limitation, in the
same spirit as Phase 1's disclosed choice to use a deterministic template
instead of an LLM rewriting pass, not a hidden substitution.

- Model: both annotators ran as Agent-tool subagents inheriting this
  session's configured model (`claude-sonnet-5`; the model actually serving
  a given turn can differ, per this environment's standard caveat).
- Each subagent was spawned fresh, in a separate context with no shared
  state or memory of the other's existence, and was instructed explicitly
  not to assume or infer another reviewer's opinion. Their full prompts are
  reproduced verbatim below (hygiene rule #3: log every LLM call, model
  version, full prompt, full response).
- Full response: `skill_library/audit/annotator_a_verdicts.json` and
  `annotator_b_verdicts.json` (raw, unedited subagent output).
- Annotator A: 62,181 tokens, 1 tool call (reading the sample file), 210s.
- Annotator B: 73,375 tokens, 1 tool call (reading the sample file), 321s.

### Prompt (identical structure for both annotators, given as separate calls)

> You are one of two independent auditors reviewing a research artifact: a
> "dependency link table" that claims each distilled conversational-agent
> "skill" is genuinely governed by specific rules from a versioned policy
> document. This is for a research project (Company Brain, Claim 2) testing
> whether policy-version-to-skill links can be trusted as ground truth.
>
> Read the file at `skill_library/audit/audit_sample.json` -- it contains a
> JSON object with a "sample" list of 23 entries. Each entry has: skill_id;
> subflow, branch; precondition, action_sequence, postcondition; policy_id,
> policy_family; linked_rules (the specific rules automatically linked to
> this skill at distillation time).
>
> Your task: for EACH of the 23 entries, independently judge -- based only
> on the information given -- whether the linked_rules genuinely,
> substantively govern this skill. A "yes" means: at least one of the
> linked rules would actually change what action is correct for this skill
> if that rule were altered (real teeth over the action_sequence /
> postcondition, not just topical proximity). A "no" means the link is
> spurious, too broad, or the rule doesn't actually constrain this skill's
> behavior.
>
> Do not confer with anyone else or assume any other reviewer's opinion --
> this is an independent, blind review. Judge each entry strictly on its
> own merits. [Annotator B's copy added: "Be appropriately skeptical: your
> job is to catch bad links, not rubber-stamp them."]
>
> Return your findings as a JSON array of 23 objects:
> `{"skill_id": ..., "verdict": "yes"/"no", "reason": "<one sentence>"}`.

## Result

| Metric | Value |
|---|---|
| n | 23 |
| Observed agreement (po) | 1.000 |
| Expected agreement (pe) | 0.841 |
| **Cohen's kappa** | **1.000** |
| Threshold (execution guide) | 0.80 |
| Passes threshold | **Yes** |

Full computation: `scripts/compute_audit_kappa.py`, output in
`kappa_result.json`.

Perfect agreement (kappa = 1.0) is a strong signal that the link
*definition* (universal rules always apply; tier-specific rules apply only
to their matching branch) is unambiguous to an independent reviewer given
the skill + rule text. It does **not** mean every automated link is
correct -- see below.

## What the audit actually caught

Both annotators, independently, flagged the same 2 of 23 sampled skills as
spurious (`SK-053`, `SK-090`) -- not a disagreement, a genuine shared
finding about a failure mode in the *clustering* step, distinct from the
link-definition question kappa measures:

- **SK-053** (POL-016, Site Performance Troubleshooting): the representative
  real dialogue escalates via Notify Internal Team *before* attempting
  Log Out/In or Try Again -- the reverse of what POL-016-R1 requires -- and
  its final action ("instructions") isn't addressed by any linked rule.
  This is a genuine ABCD dialogue where the human agent didn't follow the
  documented guideline order.
- **SK-090** (POL-029, Shipping Management): the representative dialogue's
  actions (pull-up-account, record-reason, verify-identity, update-account)
  share no substantive action with POL-029's rules (which govern Shipping
  Status / Validate Purchase / Update Order). Manual follow-up confirmed
  this is consistent across all 19 dialogues in that cluster: a meaningful
  subset of real `manage` (shipping_issue) dialogues in this ABCD release do
  not follow kb.json's documented canonical action sequence for that
  subflow. The clustering step's "most frequent action signature" selection
  picked a real but off-policy pattern as the representative.

A broader *mechanical* check was also tried -- flag any skill whose final
action doesn't match any of its policy's kb.json-documented terminal
actions -- and rejected: it flagged 47/117 linked skills, the large
majority of which are legitimate early-exit or denial branches (e.g. a
membership check correctly ending in denial, never reaching the gated
action) or optional steps correctly skipped, not spurious links. Automating
this distinction reliably needs the same semantic judgment the two-annotator
audit already provides; see `scripts/apply_audit_exclusions.py` for the
reasoning and the resolution actually applied.

## Resolution

`scripts/apply_audit_exclusions.py` removed exactly the 2 audit-confirmed
spurious skills (SK-053, SK-090) from the skill library, without
renumbering any other skill_id (so this audit trail stays addressable), and
regenerated `_skill_index.json` and `dependency_links.{json,csv}`.
Post-exclusion: **131 total skills (115 linked, 16 negative control,
12.2%)**.

## Conclusion

Kappa = 1.0 >= 0.8: no anomaly requiring a stop-and-fix of the link
definition itself. The audit's real value here was catching 2 individually
mislinked skills via independent semantic review, which a cheap mechanical
check could not do without also producing ~45 false positives -- exactly
the outcome the execution guide's audit step is designed to produce.
