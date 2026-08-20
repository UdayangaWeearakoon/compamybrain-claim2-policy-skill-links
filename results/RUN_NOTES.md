# Phase 4: Run Notes — Two Conditions, Raw Flag Tables, Execution Logs

**Frozen:** see `results/hashes/step4_checksums.json`
**Fingerprint (sha256 of sorted file hashes):** `1924fd17d3d90aac9a6c71ef33cb3eceb7fa1f3deaccc43ec71118b61424a69c`
**Preregistration:** `preregistration/STEP4_PREREGISTRATION.md`, committed in `d113bcb`
— **before** either detector existed in the repo.

Companion to `policy_corpus/datasheet.md` (Phase 1), `skill_library/CONSTRUCTION.md`
(Phase 2), and `ground_truth/CONSTRUCTION.md` (Phase 3).

## Scope

Step 4 produces **raw flag tables and execution logs only**. Scoring
(invalidation recall/precision), bootstrap confidence intervals, error slices,
and the two ablations are Step 5 and are deliberately not computed here — the
metric definitions and decision thresholds they will use are already fixed in
the preregistration, so Step 5 has no discretion left to exercise.

## Raw results

| | Condition A (SKILLGUARD-style) | Condition B (dependency links, section-level) |
|---|---|---|
| Population | 131 skills | 131 skills |
| Flagged | **6** | **76** |
| v1 control | 0 flagged (**calibration passed**) | n/a |
| Sanity anchor (6 skills) | **all 6 flagged** ✓ | **0 flagged** ✓ |
| Invalidated skills missed (of 40) | **40** | **0** |
| Silent wrong actions | **40** | **0** |
| Loud execution errors among misses | 0 | 0 |

Condition B additionally reports a document-level granularity (76 flagged —
see "Granularity" below).

## What each number means

**Condition A flagged 6 of 131, and that is the baseline working correctly.**
The environment genuinely did not change for any supersession case — that is
the design spine of the whole experiment — so a contract validator *should*
stay silent on them. The 6 it flagged are exactly the `select-faq`
sanity-anchor skills (SK-112…SK-117), which is the anchor doing its job:
proving the baseline is live and looking at something real, not merely
inactive. The guide's instruction was *"do not weaken the baseline to make it
lose"*, and two pieces of evidence back that up:

- **The v1 control.** The same check-set run against v1 contracts flags
  **zero** skills. A validator that flagged skills under the very contract
  version they were distilled from would be broken; the script refuses to
  report a v2 result at all if that control ever fails.
- **The excluded fourth check, excluded on measurement not convenience.** A
  value-domain conformance check was prototyped and dropped because it
  produces **151 false positives under v1**. ABCD stores action arguments as
  an untyped positional value list, while an action's arg list mixes
  enumerable slots (`payment_method`) with free-text ones (`customer_name`,
  `street_address`); a free-text address cannot be matched to its slot, so it
  gets scored against an enumerable vocabulary and fails spuriously. Adding a
  check that misfires on 151 valid v1 calls would have made the baseline
  *wrong*, not strong. The count and cause were recorded in the
  preregistration before any v2 run.

**Condition B flagged 76 of 131, and that number contains real, intended
precision loss.** It detects that a linked rule's *text* differs and makes no
attempt to tell a substantive change from a cosmetic reword — the guide's
"simplest version first". The Step 3 distractors (5 whole-document cosmetic
policies + one in-document cosmetic reword inside each real-supersession
policy) are therefore expected to drag its precision down, and they do. That
cost is the measurement the distractors were planted to produce; a detector
tuned to dodge them would be marking its own homework. Step 5 quantifies it.

**Silent wrong actions: 40 for A, 0 for B.** Every one of the 40 invalidated
skills Condition A missed replays *cleanly* against the unchanged v2
environment — zero loud errors — while violating a v2 policy rule. That is the
operational harm the claim is about: nothing crashes, nothing alerts, and the
agent confidently performs an action the current policy forbids. All 40 had at
least one applicable deterministic predicate, so the measurement covers the
invalidated class completely rather than sampling it.

## Isolation

The guide flags leakage as *"the most common silent corruption in this
experimental shape, because the same researcher built both the labels and the
detector"* — precisely this project's situation. It is enforced mechanically,
not by assertion (`scripts/validate_step4.py`):

- Condition A may not read `policy_corpus/`, `ground_truth/`, or the anchor
  description. It sees skills and contracts only.
- Condition B may not read `ground_truth/` **or** the `_change_log` field
  inside each v2 policy document — that field carries
  `change_type: real_supersession | cosmetic_reword`, which *is* the answer
  key for the distractor set. `load_rules()` discards every key except
  `rule_id` and `statement` at the data boundary, so it cannot leak in
  accidentally.
- The validator statically analyses both sources (AST walk over `open()`/
  `glob()` arguments, module-level path constants, and literal subscript keys)
  and fails the build on any forbidden access.
- `scripts/test_leakage_check.py` proves that check actually fires, by
  injecting each realistic leak path into a throwaway copy of Condition B and
  asserting rejection. A leakage check that never fires would pass just as
  happily on a corrupted pipeline.

Only `measure_silent_wrong_action.py` reads ground truth, which the guide's
own definition of the metric requires ("invalidated skills that each condition
*failed to flag*"). It consumes both flag tables as finished, frozen inputs
and feeds nothing back.

## Findings recorded for Step 5

1. **The granularity ablation has no headroom on this corpus.** Section-level
   and document-level Condition B flag *identical* skill sets (0 differing of
   131). The cause is structural: Step 3's in-document cosmetic reword always
   lands on the first non-superseded rule, which in this corpus is a universal
   rule present in every skill's dependency link — so any document-level
   change also reaches section level. Step 5 should report this as a property
   of the corpus's rule-sharing density, **not** as a null result, and should
   not present a table implying the two granularities were meaningfully
   compared. Surfaced in `results/condition_b/flags.json` via
   `granularity_agreement`, computed from Condition B's own output only.
2. **One planted distractor is inert.** Condition B detects 51 changed rules;
   Step 3 planted 20 real + 32 cosmetic = 52. The missing one is
   `POL-002-R2`, whose cosmetic reword produced *no text change at all*
   because the fixed 4-pair synonym table matched nothing in that rule's
   wording. It is correctly not counted as changed. The effective distractor
   count is therefore 31 in-corpus rewords, not 32.
3. **Condition B's perfect recall comes with breadth.** It missed 0 of 40
   invalidated skills, but flagged 76 of 131 overall. Recall and precision
   must be read together in Step 5; the recall figure alone overstates the
   result.

## Known limitations

- **"Execution" is a faithful replay, not a live environment run.** ABCD ships
  dialogues and gold action sequences, not an executable customer-service
  backend, so there is no process to actually run. The replay validates the
  recorded gold sequence against the v2 contract (execution succeeds/errors)
  and then against deterministic v2-policy predicates (right/wrong action).
  This preserves the distinction the metric depends on — *completes without
  error* vs *produces the wrong action* — but it is a simulation of execution,
  and a live-environment harness could surface failure modes this cannot.
- **Check A3 assumes a newly-introduced parameter breaks existing calls.**
  In general a new parameter might be optional; here the anchor documents it
  as required, and ABCD's untyped positional value lists mean a recorded call
  can never bind a parameter that did not exist when it was recorded. The
  assumption is stated in the preregistration rather than buried in code.
- **Condition B is the naive version by design.** Any improvement (semantic
  change classification, diff-significance thresholds) would raise precision
  and is explicitly deferred — the guide asks for the simplest version first
  so the headline comparison is not confounded by detector tuning.
- **The value-dependent (Partial) class is not exercised by the silent
  wrong action measurement.** SWA is defined over *invalidated* skills only,
  per the guide. Partial skills carry the value-dependent rules, whose
  correctness depends on each dialogue's concrete numbers — the same
  simplification already flagged in `ground_truth/CONSTRUCTION.md`. Step 5's
  error slices are where that class gets its scrutiny.

## Reproducibility

Every Step 4 script is deterministic: no sampling, no randomness, no model
calls, so there is no seed to fix and nothing to log under the LLM-call
hygiene rule. Re-running any script on the frozen inputs reproduces its output
byte-for-byte; each was in fact re-run inside the repository after transfer and
produced identical results. No LLM-as-judge is used anywhere in Step 4, so the
guide's 50-hand-labeled-case judge validation is not applicable by
construction — recorded as such rather than skipped. Step 5's bootstrap *will*
need a fixed seed.

**Contamination.** ABCD is public and dates from 2021, so any model touching
this pipeline has plausibly seen the dialogues. This does not threaten the
result: the object under test is the v1→v2 policy supersession authored in
Step 3, which exists in no training corpus. Stated in the preregistration
before results existed, not in response to review.
