# Claim 2 — Step 4 Preregistration

**Written and committed before either condition was implemented or run.**
Execution guide, Step 4: *"Preregister everything first. Write the exact
detection procedures, metrics, and thresholds in one document before running
either condition. Commit it with a timestamp."*

| | |
|---|---|
| Claim | Skill drift detection scoped to environment contracts cannot detect knowledge supersession; explicit policy-version-to-skill dependency links can. |
| Baseline | SKILLGUARD-style environment-contract validation (arXiv 2605.10990) |
| This document fixes | detection procedures, metric definitions, decision thresholds, isolation protocol |
| Scope | **Step 4 only**: produce raw flag tables and execution logs. Scoring, bootstrap CIs, error slices, and ablation *analysis* are Step 5 and are deliberately not performed here. |

## 1. Frozen inputs

Step 4 consumes only artifacts already frozen and hashed in Steps 1–3. No input
is modified by this step.

| Artifact | Fingerprint |
|---|---|
| Policy corpus v1 (37 policies, 123 rules) | `dd94cf1c9567fed864126bc48c7bd954e7643033037da4fff704d1b9b7441d87` |
| Skill library v1 (131 skills, 115 linked + 16 negative control) | `4a1aea880cb1d5abafe40864a5919a4bf91b37ec5c3a92c3f1331ef5cc48e4e4` |
| Policy corpus v2 + ground truth + environment contracts | `dc164882823bde7c12f3e1bd20bd38f969b8dbeacd7fd25bfc3f157d1b281618` |

Population under test: all **131** skills. Ground truth (Step 3): 40
invalidated, 22 partial, 69 valid (across the full library, including the 16
always-valid negative controls).

## 2. Condition A — SKILLGUARD-style contract validation (baseline)

**Procedure.** For every skill, for every step in its recorded
`action_sequence`, validate the call against the *current* environment
contract (`environment_contracts/v2_action_schemas.json`). A skill is flagged
if any step fails any check below. Three checks, all structural:

- **A1 — unknown action.** The step's `button` does not exist in the current
  contract. (Catches a removed or renamed tool.)
- **A2 — arity overflow.** The step supplies more values than the action's
  contract permits (`len(values) > len(contract_args)`).
- **A3 — unsatisfied newly-introduced parameter.** The action's current
  signature contains one or more parameters absent from the signature the
  skill was authored against (v1). A recorded call carries an unlabeled,
  positional value list and therefore provides no binding for a parameter that
  did not exist when it was recorded, so any call to such an action fails.

**Baseline strength — not weakened.** The guide is explicit: *"Do not weaken
the baseline to make it lose."* Two commitments:

1. Condition A is run against **v1 contracts as a control** in the same
   execution, and must produce **zero** flags. A validator that flags skills
   under the very contract version they were distilled from is broken, and a
   zero-flag control is the evidence that A1–A3 are correctly calibrated
   rather than arbitrarily permissive.
2. A fourth candidate check — **value-domain conformance** (every supplied
   value must belong to the enumerated vocabulary of an argument slot the
   action accepts, per ABCD `ontology.json` `values.enumerable`) — was
   prototyped and **excluded on measured evidence**, not on convenience: it
   produces **151 violations under v1**, all false positives. Cause: ABCD
   records action arguments as an *untyped positional value list*, while an
   action's arg list mixes enumerable slots (e.g. `payment_method`) with
   non-enumerable free-text slots (e.g. `customer_name`, `street_address`).
   A free-text value such as an address or account ID cannot be matched to
   its slot, so it is scored against the enumerable vocabularies and fails
   spuriously. Including a check that misfires on 151 valid v1 calls would
   make the baseline *wrong*, not strong. The exclusion, its measured count,
   and its cause are recorded here **before** any v2 run.

**Isolation.** Condition A reads only the skill library and
`environment_contracts/`. It must not read `policy_corpus/`, `ground_truth/`,
or the anchor description.

**Predicted outcome (recorded before running).** Near-zero flags on
supersession cases — the environment did not change for them — and a correct
flag on the sanity anchor: the 6 skills invoking `select-faq`
(SK-112…SK-117). This is the baseline behaving exactly as designed, not
failing.

## 3. Condition B — dependency-link detector (intervention)

**Procedure.** For each policy that has a v2 document, compare v1 and v2 rule
statements **by `rule_id`**. Any rule whose statement text differs is a
*changed rule*. Follow the Phase 2 dependency link table from each changed
rule to the skills recorded under it, and flag those skills.

Two granularities are emitted; **section-level is the primary condition**, per
the guide's *"follow the dependency links from the changed policy sections to
the skills distilled under them"*:

- **B-section (primary).** Flag a skill iff at least one of the specific
  `rule_id`s in its dependency link changed.
- **B-document (ablation input).** Flag a skill iff *any* rule in its linked
  policy document changed. Emitted as raw output only; the guide assigns the
  granularity comparison to Step 5 ("record section level granularity as an
  ablation for later"), so no comparison is drawn here.

**Deliberately naive.** The guide says: *"Implement the simplest version
first: any linked skill under a superseded section gets flagged."* Condition B
therefore does **not** attempt to distinguish a substantive rule change from a
cosmetic reword. It sees only that the text of a linked rule differs. The 5
cosmetic-only distractor policies and the 18 in-document cosmetic rewords
planted in Step 3 are expected to cause **real precision loss**, and that loss
is the honest measurement the distractors were planted to produce. Suppressing
it would be the experiment marking its own homework.

**Isolation — mechanically enforced.** Condition B must never read the ground
truth label table. It is additionally forbidden from reading the
`_change_log` field inside each v2 policy document, because that field carries
`change_type: real_supersession | cosmetic_reword` — injection-time metadata
that *is* the answer key for the distractors. Condition B loads only
`policy_id`, `version`, and `rules[].{rule_id, statement}` from v1/v2, plus
`skill_library/dependency_links.json`. A validator (`validate_step4.py`) greps
the Condition B source for `ground_truth`, `labels`, and `_change_log` and
fails the build if any appears.

**Predicted outcome (recorded before running).** Flags every invalidated and
partial skill whose linked rule changed; also flags valid skills under
cosmetically-edited rules (precision loss); does **not** flag the 6 sanity-
anchor skills, since POL-036/POL-037 have no v2 at all.

## 4. Silent wrong action rate

**Definition (guide).** *"Take invalidated skills that each condition failed
to flag. Execute them against ABCD gold action sequences under the v2 policy.
Every execution that completes without error but produces the wrong action is
a silent wrong action."*

**Operationalisation.** For each **invalidated** skill a given condition did
not flag, replay its recorded action sequence:

1. **Execution check.** Validate the sequence against the v2 environment
   contract (the Condition A check-set). If it fails, the execution *errored*
   — loud failure, not silent.
2. **Correctness check.** Evaluate the sequence against a deterministic
   compliance predicate for each v2 rule that superseded one of its linked
   rules.
3. A replay that **passes (1) and fails (2)** is a **silent wrong action**:
   it runs cleanly against an unchanged environment and produces an action the
   current policy forbids.

**Compliance predicates (fixed here, before running).** All 13 superseded
`hard` rules reduce to mechanical checks over the recorded sequence:

| v2 rule(s) | Predicate for compliance |
|---|---|
| POL-001-R1, POL-002-R1, POL-003-R1 | a `validate-purchase` step supplies ≥ 4 values (v2 adds a 4th required field) |
| POL-005-R1, POL-006-R1, POL-007-R1, POL-008-R1, POL-009-R1, POL-010-R1, POL-011-R1, POL-012-R1 | a `verify-identity` step supplies ≥ 4 values |
| POL-004-R3 (guest returns never eligible) | a guest-branch sequence must not reach the return-granting step (`update-order`) |
| POL-035-R3 (Bronze/Guest denied, Oracle no longer consulted) | a bronze/guest-branch sequence must not call `ask-the-oracle` |

**No LLM-as-judge is used anywhere in Step 4.** Every judgment above is a
deterministic predicate over recorded data. The guide's requirement — *"if any
judgment uses an LLM as judge, validate the judge against 50 hand-labeled
cases first and report its agreement"* — therefore does not bind, and is
recorded here as *not applicable by construction* rather than silently
skipped. If any later step introduces an LLM judge, that validation is owed
before it is trusted.

## 5. Metric definitions (computed in Step 5, defined here)

Over the skill population, per condition:

- **Invalidation recall** = flagged ∩ invalidated ÷ invalidated.
- **Invalidation precision** = flagged ∩ invalidated ÷ flagged.
- **Silent wrong action rate** = silent wrong actions ÷ invalidated.

`partial` is scored as a separate class and is **not** folded into
`invalidated` for the primary recall figure; a partial-inclusive variant may
be reported alongside as a secondary cut. Fixing this here prevents a
favourable post-hoc choice of denominator.

## 6. Preregistered decision thresholds

From the team claims file, fixed before any Claim 2 data existed:

> *Claim 2 fails if dependency links add no recall over contract validation.
> It holds if they catch supersession cases contracts miss, at comparable
> precision.*

Applied mechanically in Step 5:

- **FAILS** if `recall(B) ≤ recall(A)` on invalidated skills.
- **HOLDS** if `recall(B) > recall(A)` **and** `precision(A) − precision(B) ≤
  5 percentage points` (the guide's "five points is a defensible choice").
- **PARTIAL** if recall improves but the precision drop exceeds 5 points —
  reported as partial, not silently upgraded to a hold.

## 7. Seeds, logging, contamination

- **Seeds.** Every Step 4 procedure is deterministic — no sampling, no
  randomness, no model calls. There is no seed to fix; re-running any script
  on the frozen inputs reproduces its output byte-for-byte. (Bootstrap
  resampling in Step 5 *will* need a fixed seed.)
- **LLM call log.** No LLM calls are made in Step 4. Nothing to log.
- **Contamination.** ABCD is public and dates from 2021, so any model touching
  this pipeline has plausibly seen the dialogues. This is acceptable and does
  not threaten the result: the object under test is the **v1→v2 policy
  supersession**, authored in Step 3 and existing nowhere in any training
  corpus. Detection performance is measured against those novel policy
  versions, not against recall of ABCD itself. Stated here explicitly, before
  results exist, rather than in response to review.

## 8. Design-time inspection disclosure

Honest accounting of what had been looked at when this document was written:
the Condition A check-set was calibrated against the **v1 control** (which
uses no ground truth and no v2 outcome), which is how the 151 false positives
of the excluded value-domain check were measured; and the 13 hard-rule
compliance predicates were derived by reading the v2 rule text and the
recorded action sequences. **No condition had been run against the v2
contracts or the v2 policy corpus, and no flag table existed, when this
document was committed.** The decision thresholds in §6 predate the entire
claim's execution.
