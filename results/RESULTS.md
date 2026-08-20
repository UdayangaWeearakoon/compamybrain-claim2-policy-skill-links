# Claim 2 — Phase 5 Results

**Claim.** Skill drift detection scoped to environment contracts cannot detect
knowledge supersession. Explicit policy-version-to-skill dependency links
detect skills invalidated by an organizational policy change that leaves the
environment unchanged.

**Baseline.** SKILLGUARD-style contract validation (arXiv 2605.10990).

**Verdict against the preregistered threshold: HOLDS.**

All metric definitions, the partial-class denominator, and the decision rule
were fixed in `preregistration/STEP4_PREREGISTRATION.md` before either
condition ran (commit `d113bcb`, ahead of every detector in the repo). Phase 5
implements them; it does not get to choose them.

## Main results

Population: 131 skills (40 invalidated, 22 partial, 69 valid). Bootstrap:
1000 resamples over skills, seed `20260820`, percentile CIs.

**Primary — `partial` scored as a separate, non-positive class.**

| Condition | Invalidation recall | Invalidation precision | Silent wrong action rate |
|---|---|---|---|
| A — SKILLGUARD contract validation | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | **1.000** [1.000, 1.000] |
| B — dependency links (section-level) | **1.000** [1.000, 1.000] | 0.526 [0.405, 0.644] | **0.000** [0.000, 0.000] |

**Secondary — `partial` folded into the positive class** (preregistered as a
companion cut, never a replacement):

| Condition | Recall | Precision | Silent wrong action rate |
|---|---|---|---|
| A | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] |
| B | 1.000 [1.000, 1.000] | **0.816** [0.725, 0.896] | 0.000 [0.000, 0.000] |

The zero-width recall intervals are correct rather than suspicious: Condition B
flags *every* invalidated skill and Condition A flags *none*, so no resample of
the population can move either figure.

### The decision, applied mechanically

- recall(B) = 1.000 > recall(A) = 0.000 → **recall improved**
- precision drop (A − B) = **−52.6 points**, bound 5.0 → **within bound**
- **Verdict: HOLDS.**

### One caveat that matters more than the verdict

Condition A's precision is 0.000 because it made zero true-positive
*invalidation* detections while flagging 6 skills — and those 6 flags are its
**correct** environment-drift detections (the `select-faq` sanity anchor),
which the invalidation label set scores as non-positives because no policy
governing them changed.

Condition A is not malfunctioning and was not weakened. It flagged 0 skills on
the v1 calibration control, and a candidate fourth check was excluded on
measured evidence (151 false positives under v1) rather than convenience. It is
being measured on an axis it does not observe. The precision half of the
threshold is therefore satisfied *trivially, not informatively*, and this
result should be reported that way. The honest headline is the recall and
silent-wrong-action columns, not a precision win.

## Silent wrong action: what the baseline's blindness costs

Every one of the 40 invalidated skills Condition A missed replays **cleanly**
against the unchanged v2 environment — zero loud errors — while violating a v2
policy rule. Nothing crashes, nothing alerts, and the agent confidently
performs an action current policy forbids. That is a silent wrong action rate
of **1.000** for contract validation against **0.000** for dependency links,
and it is the operational statement of the claim: the failure is not that the
baseline is noisy, but that it is *silent*.

## Condition B's error structure

Sliced before any of this interpretation was written
(`results/scoring/condition_b_error_slice.json`).

| | Count |
|---|---|
| False negatives | **0** |
| False positives | 36 |
| — of which `partial` | **22 (61.1% of all error mass)** |
| — of which `valid` (cosmetic-only distractors) | 14 |

The Phase 5 spec anticipated that partial invalidation would dominate, and it
does — at 61.1% — but in the **false-positive** direction rather than as
misses. Condition B misses nothing; its entire error mass is over-flagging.

The mechanism is exactly the predicted one. Flagged partial skills link to 3–4
rules each, of which only 2 changed, and the change that landed is
*value-dependent* — wrong only for inputs past a new threshold. A section-level
link can say "a rule you depend on changed." It cannot say "that rule changed,
but only for some inputs." So the detector fires on skills that are not
universally invalid.

This is a **granularity limitation, not a defect in the linking idea**, and it
is what motivates the first ablation. Note also that these 22 count as errors
only under the primary convention; under the preregistered secondary cut they
are true positives, which is the entire distance between precision 0.526 and
0.816.

## Ablation 1 — link granularity (document vs section)

| Arm | Recall | Precision | Flagged |
|---|---|---|---|
| Document-level | 1.000 | 0.526 | 76 |
| Section-level | 1.000 | 0.526 | 76 |

**There is no tradeoff on this corpus — the two arms flag identical skill sets
(0 of 131 differ).** Reported as measured rather than reshaped into a curve.

The null is diagnosed rather than left bare. The granularities can diverge only
for a skill whose policy changed a rule it does *not* link to **and** which
links to no other changed rule. In this corpus:

- 71 skills link to **every** changed rule in their policy;
- 5 skills genuinely *do* have an unlinked changed rule (the tier-gated cases) —
  so the collapse is not the trivial artifact of every skill linking everything;
- but those 5 still hit *other* changed rules, leaving the divergence set empty.

Root cause: Step 3's in-document cosmetic reword always lands on the first
non-superseded rule, which is universal and therefore present in every skill's
dependency link. This is a property of the corpus's **rule-sharing density**,
not evidence that granularity is irrelevant. A corpus whose changes land on
tier-specific or otherwise narrowly-linked rules would separate the two arms
immediately — and the 22-skill partial-class error mass above is precisely the
population a finer-than-section granularity would need to address.

## Ablation 2 — remove the negative controls

| Detector | Precision (with) | Precision (without) | Inflation | Negative controls flagged |
|---|---|---|---|---|
| Condition B | 0.526 | 0.526 | **0.0 pts** | **0 / 16** |
| Link-free counterfactual | 0.320 | 0.367 | **+4.7 pts** | **16 / 16** |

Removing the negative controls moves Condition B's precision by exactly zero,
and that is arithmetic rather than luck: negative controls carry no dependency
link, Condition B never flags them, so they are *true negatives* — and
precision (TP ÷ flagged) does not read true negatives at all. The expectation
that precision would inflate silently assumes a detector that fires on them.

So the ablation supplies one. The counterfactual arm is a **link-free
action-overlap heuristic** — flag any skill sharing an action button with a
skill under a changed rule — the kind of behavioural/topical proxy reached for
when explicit dependency links do not exist. It flags 125 of 131 skills
including **all 16** negative controls, and removing them inflates its
precision by 4.7 points.

That contrast is the real justification for planting them: the negative
controls are a falsification test for over-triggering that Condition B passes
and a plausible alternative fails. Without them in the population, a detector
of the second kind would have looked more precise than it is, and nothing in
this experiment would have exposed it.

## Placing the result in the shared gap

The team's shared gap is that governance signals attached to source knowledge
are not carried across the derivation boundary. Claim 2's result gives that
gap a concrete, measured shape: the two conditions are not competing detectors
that happen to differ in accuracy — they are watching **different axes**, and
each is blind on the other's. Contract validation governs the *environment*:
it reads tool signatures, and it correctly caught all six anchor skills when a
tool argument changed, while flagging nothing when policy moved underneath 40
skills whose environment was untouched. Dependency links govern the
*derivation boundary*: they read which policy version a skill was distilled
under, and they caught all 40 supersessions while remaining silent on the
anchor, whose policies never changed. Neither signal is a degraded version of
the other, and neither subsumes the other — a system running only the baseline
carries a 100% silent wrong action rate on supersession, while a system running
only dependency links would miss every genuine environment break. That
orthogonality is what carries into the Claim 4 integration experiment: because
the two signals are independent and each has a blind spot the other covers,
they are candidates for the single inheritance operator Claim 4 proposes —
where a derived node carries both the minimum validity and the policy version
of its inputs — rather than two overlapping checks whose composition would be
redundant.

## Threats to validity

- **The precision comparison is not informative**, for the reason given above.
  The claim rests on recall and silent wrong action, where the separation is
  unambiguous, not on out-precisioning a detector that makes no detections on
  this axis.
- **Condition B is deliberately naive**, per the guide's "simplest version
  first". Its 14 cosmetic-only false positives are a tuning artifact, not a
  property of dependency links: any change-significance filter would remove
  them. The reported precision is therefore a *floor*, not an estimate of what
  the mechanism can achieve.
- **Ceiling effects.** Recall of exactly 1.000 with zero-width intervals means
  this corpus does not stress the mechanism's limits. A harder corpus — changes
  landing on narrowly-linked rules, or skills whose link sets are sparser —
  would be needed before treating 1.000 as an estimate of real-world recall.
- **The corpus is synthetic in its supersessions.** The v1→v2 changes were
  authored in Step 3 for this experiment. That is what makes them
  uncontaminated (see the preregistration's contamination argument), but it
  also means the distribution of change types is a design choice, not a
  natural frequency — and the granularity collapse in Ablation 1 is a direct
  consequence of one such choice.
- **`partial` handling drives the headline precision number** more than any
  other single decision (0.526 vs 0.816). It was fixed in advance precisely so
  it could not be chosen after the fact, and both cuts are reported.

## Provenance

| Artifact | Fingerprint |
|---|---|
| Policy corpus v1 | `dd94cf1c9567fed864126bc48c7bd954e7643033037da4fff704d1b9b7441d87` |
| Skill library v1 | `4a1aea880cb1d5abafe40864a5919a4bf91b37ec5c3a92c3f1331ef5cc48e4e4` |
| Policy corpus v2 + ground truth | `dc164882823bde7c12f3e1bd20bd38f969b8dbeacd7fd25bfc3f157d1b281618` |
| Step 4 preregistration + flag tables | `1924fd17d3d90aac9a6c71ef33cb3eceb7fa1f3deaccc43ec71118b61424a69c` |
| Phase 5 scoring outputs | see `results/hashes/step5_checksums.json` |
