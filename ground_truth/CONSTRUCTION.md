# Phase 3: Construction Notes — v2 Corpus, Ground Truth, Distractors, Sanity Anchor

**Frozen:** see `policy_corpus/hashes/v2_checksums.json`
**Fingerprint (sha256 of sorted file hashes):** `dc164882823bde7c12f3e1bd20bd38f969b8dbeacd7fd25bfc3f157d1b281618`

Companion to `policy_corpus/datasheet.md` (Phase 1) and `skill_library/CONSTRUCTION.md`
(Phase 2), for the same reason: don't leave construction reasoning for the end.

## What this phase built

Per the execution guide's Step 3 ("Inject Supersessions and Plant Ground Truth"):
a v2 policy corpus, a frozen ground-truth label table, a distractor set, and one
environment-drift sanity anchor — the event the two detectors in Step 4 must be
told apart by.

## 1. Selecting what to supersede (`scripts/select_supersessions.py`)

Deterministic, no randomness. Every v1 rule was classified from its own text:
a rule mentioning a numeric threshold (dollar amount, day count, percentage) is
`value_dependent`; every other rule is `hard`. Real skill dependency links from
Phase 2 (`skill_library/v1/*.json` `rule_ids`) — not text re-derivation — were
used to compute exactly which skills each candidate rule change would reach.

**The guide's two Step 3 targets are in real tension for this corpus, and that
tension is disclosed here rather than papered over.** The guide asks for both:
(a) "roughly 40 percent invalidated, 20 percent partial, 40 percent valid" across
the skill library, and (b) v2 documents for "30 to 50 percent of policy
documents." Phase 2's actual skill distillation produced a skill library with
low per-policy density — 25 of 37 policies have exactly 3 linked skills, 8 have
4, and 4 have 2 (`skill_library/v1/_skill_index.json`). Hitting target (a) means
labeling roughly 52 skills invalidated and 26 partial (78 of 115 linked skills,
~68%) — but spending only 30-50% of policies (11-19 of 37) caps the reachable
skill count at 62 even if every one of the 18 largest policies were spent on a
single bucket each. The two targets cannot both be hit exactly on this corpus;
this was discovered by direct computation, not assumed.

**Resolution:** class balance was prioritized, since the guide gives it an
explicit statistical justification ("heavy imbalance makes recall numbers
unstable") that the policy-percentage target doesn't carry. The selection was
capped at exactly 18 real-supersession policies — 48.6%, at the top of the
guide's 30-50% band — and the achieved class split was accepted as whatever
that cap allows, rather than pushing policy count past 50% to force an exact
78-skill split. Where a policy is tier-gated with a rule scoped to only some
branches, one hard (branch-scoped) rule and one value-dependent (all-branch)
rule are superseded together in the *same* policy when it usefully splits that
policy's skills across both buckets instead of spending two separate policies
(done for POL-004 and POL-035) — this is what let 18 policies reach further
than 18 independent single-purpose picks would have.

**Achieved (18 real-supersession policies, 20 rule-level supersession
actions):**

| | invalidated | partial | valid | total |
|---|---|---|---|---|
| Linked skills (115) | 40 (34.8%) | 22 (19.1%) | 53 (46.1%) | 115 |
| Full library (131, incl. 16 negative controls) | 40 (30.5%) | 22 (16.8%) | 69 (52.7%) | 131 |

Partial landed almost exactly on target (19.1% vs. 20%); invalidated and valid
are each off by roughly 5-6 points from the 40/40 target, in the direction the
density constraint predicts (fewer invalidated, more valid, since the policy
cap left real capacity unused rather than overshoot it). This is a documented,
reasoned deviation, not an unexplained gap.

## 2. Writing the v2 rule text (`scripts/build_policy_corpus_v2.py`)

Every superseded rule's new text is a **hand-authored, genuine behavioral
change** (`REAL_REWRITES` in the script), not a template mutation, because the
whole point of ground truth here is that the new text must actually flip the
correct action for skills that depend on it. Two change families were used,
matching the `hard` / `value_dependent` split from selection:

- **Hard (11 rules):** mostly "verification hardening" — nine identity/purchase
  -validation rules (`Verify Identity` / `Validate Purchase`) gain a 4th
  required field (phone number) that no recorded skill's action sequence
  supplies, so any skill depending on the old 3-field requirement is now
  unconditionally wrong. `POL-012-R1` raises a 3-of-4-items rule to 4-of-4 the
  same way. `POL-004-R3` and `POL-035-R3` remove a conditional Oracle/window
  check in favor of an unconditional denial for the branch they gate.
- **Value-dependent (9 rules):** numeric threshold changes only — return
  windows, dispute-refund dollar amounts, day-count eligibility cutoffs, late-
  payment allowances. Each is a plausible, self-contained policy recalibration
  (e.g. `POL-025-R1`'s "more than 7 days" -> "more than 14 days"). Whether a
  given historical dialogue's actual value crosses the new threshold varies by
  case, which is exactly why these are labeled Partial rather than Invalidated.

Every change is logged in that policy's own `_change_log` field (v1 text, v2
text, and a one-line note on why it's a genuine flip) — inspectable per rule,
not just asserted in this document.

## 3. Distractors (cosmetic-only edits, alter no behavior)

Two distinct distractor mechanisms, both required to pass a mechanical
`verify_cosmetic()` check before being written (it strips the fixed
connector-word substitutions back out of both the old and new text and
requires the residues match — a real guarantee, not a claim taken on faith):

- **In-document distractors (18, one per real-supersession policy):** exactly
  one *other* rule in each real-supersession v2 document — never the rule that
  was actually superseded — gets a connector-word reword ("must" ->
  "is required to", "before" -> "prior to", etc.) plus the whole rules array is
  reordered. This is the case the guide's "alongside real supersessions, inject
  cosmetic edits" describes literally: a v2 document that changed *some* text
  contains both a real behavioral change and unrelated noise, and a text-diff
  detector that reacts to any changed line would wrongly implicate the
  cosmetically-reworded rule's skills too.
- **Whole-document-only distractors (5 policies: POL-013, 014, 015, 016,
  018):** chosen deterministically (first 5 policies, in ID order, that
  `select_supersessions.py` never touched). Every rule keeps its exact v1
  testable content; only wording and rule order change. These are a policy
  version bump with zero substantive content change — the strongest test that
  a detector doesn't over-trigger on "the document text changed at all."

Neither kind of cosmetic edit ever contributes a rule_id to the "superseded"
set used for labeling (`label_ground_truth.py`), so every skill under a
cosmetic-only or in-document-cosmetic-only rule is labeled Valid by
construction, and `scripts/validate_phase3.py` checks this mechanically for
every skill, not just spot-checks it.

14 policies (POL-019, 021-024, 026-029, 031-033, 036, 037) received no v2 at
all and remain v1-only.

## 4. Ground-truth labels (`scripts/label_ground_truth.py`)

Per-skill label logic, computed independently of (but designed to exactly
reproduce) the selection plan's own simulation:

- Negative-control skills (16, no policy link by construction) -> **Valid**.
- Skill's policy has no v2, or only a cosmetic-only v2 -> **Valid**.
- Skill's policy has a real-supersession v2: intersect the skill's linked
  `rule_ids` with that policy's superseded rule_ids.
  - Intersection empty -> **Valid**.
  - Intersection contains >=1 `hard`-type superseded rule -> **Invalidated**.
  - Intersection non-empty and entirely `value_dependent` -> **Partially
    invalidated**.

The script asserts its own output matches `_supersession_plan.json`'s
`achieved_counts` exactly (not eyeballed) before writing `labels.json`/`.csv`.
Every row carries a plain-language `reason` naming which rule(s) fired and why
— this is what Step 4/5 error-slicing will read.

## 5. Sanity anchor (`scripts/build_environment_contract_anchor.py`)

The guide's "one environment drift case": a pure API/tool-contract change,
independent of any policy. ABCD's `ontology.json` "actions" field is the
environment-contract analog here (per-tool argument schemas). The `select-faq`
tool's v1 signature (`['single_item_query', 'storewide_query']`) gains a new
required argument, `topic_category_id`, in v2 — nothing about this is a policy
text change.

**Isolation is deliberate and checked, not assumed:** `select-faq` is used by 6
skills (SK-112 through SK-117), all under POL-036 / POL-037 — both of which are
in the untouched-14 set, never receiving any v2 (real or cosmetic) in this
phase. `scripts/validate_phase3.py` asserts the anchor's impacted policies are
a subset of the untouched set, so this case can never be confounded with a
policy-driven label. Expected Step 4 behavior (not run in this phase): Condition
A (SKILLGUARD-style contract validation) should flag all 6, since their
recorded calls omit the new required argument; Condition B (the dependency-link
detector) should not, and correctly won't, since no policy version linked to
POL-036/POL-037 changed — ground truth keeps all 6 at Valid.

## Final composition

- **Policies:** 18 real-supersession (48.6%), 5 cosmetic-only-distractor
  (13.5%), 14 untouched (37.8%). 23/37 (62.2%) received some v2 document; 18/37
  (48.6%) received a document with real behavioral content.
- **Rule-level supersession actions:** 20 (11 hard, 9 value-dependent) across
  18 policies.
- **Ground truth labels (115 linked skills):** 40 invalidated, 22 partial, 53
  valid. Across the full 131-skill library (including 16 negative controls,
  always Valid): 40 invalidated, 22 partial, 69 valid.
- **Sanity anchor:** 1 environment-contract case (`select-faq`), 6 skills,
  cleanly isolated from every policy-driven label.

## Known limitations

- **The 40/20/40 class-balance target is not exactly met**, for the structural
  density reason documented above (Section 1) — invalidated and valid are each
  roughly 5-6 points off target, partial is on target. This is a property of
  the real skill library Phase 2 actually produced, not a labeling error;
  Step 5's confidence intervals should be read with the true (not the
  idealized target) class sizes.
- **Rewrite authorship is a disclosed substitute for the guide's implicit
  "author it carefully" step**, in the same spirit as Phase 1 and Phase 2's
  disclosed LLM-substitution choices: the 20 real rule changes were
  hand-authored by the assistant executing this phase (not LLM-generated at
  distillation time, not human-reviewed by a second party) and are inspectable
  verbatim in each `_change_log`, but they have not been independently audited
  the way Phase 2's skill-policy links were (two-annotator kappa). A future
  pass could apply the same audit pattern to the v2 rewrites specifically.
- **The "hard" vs. "value_dependent" split is itself a simplifying
  operationalization** of the guide's Invalidated/Partial distinction ("wrong
  only on certain inputs"), not a per-dialogue value simulation. A rule is
  treated as Partial for every skill that references it once superseded,
  without checking whether that specific skill's actual recorded values (e.g.
  the specific dollar amount in its trace) individually cross the new
  threshold. Confirming that would require re-running the threshold check
  against each skill's concrete `action_sequence` values — feasible, but out
  of scope for label-table construction; flagged here as a natural Step 4/5
  robustness check if results look sensitive to it.
- **The in-document cosmetic reword is a fixed 4-pair synonym table**
  (must/is required to, before/prior to, may/is permitted to, if/in the event
  that), applied at most once per document. It is mechanically verified to
  preserve testable content, but it is not stylistically diverse — a
  sufficiently sophisticated style-only classifier could probably learn to spot
  the substitution pattern itself, the same limitation Phase 1's datasheet
  already flags for template-based text in general.
