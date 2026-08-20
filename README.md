# Company Brain — Claim 2: Policy-Version-to-Skill Dependency Links

**Claim:** Skill drift detection scoped to environment contracts (SKILLGUARD-style
contract validation) cannot detect knowledge supersession caused by an
organizational policy change that leaves the environment unchanged. Explicit
policy-version-to-skill dependency links, recorded at skill-derivation time,
can.

**Baseline:** SKILLGUARD-style environment-contract validation
([arXiv:2605.10990](https://arxiv.org/abs/2605.10990)) — 100% precision / 76%
recall on DRIFTBENCH (known environment drift).

**Variables:** invalidation recall, invalidation precision, silent wrong
action rate.

**Preregistered falsifiable threshold:** the claim fails if dependency links
add no recall over contract validation. It holds if they catch supersession
cases contracts miss, at comparable precision (precision drop within 5
points).

**Substrate corpus:** [ABCD](https://arxiv.org/abs/2104.00783) (Chen et al.
2021) — 10k human-to-human customer service dialogues, 55 intents, gold
action sequences, written agent guidelines, MIT license.

This repo implements the five-step execution guide for Claim 2, from raw
policy corpus to final result table, as one of four claims under the shared
Company Brain gap: governance signals attached to source knowledge (read
permissions, validity timestamps, policy versions) are not carried across the
derivation boundary into derived artifacts (summaries, skills).

## Repository layout

```
abcd-master/       ABCD dataset code + small guideline/taxonomy files (tracked)
                    Large raw dialogue files are gitignored -- see "Getting the data"
policy_corpus/      Versioned policy corpus distilled from ABCD's agent guidelines
  v1/               37 frozen v1 policy documents (123 testable rules), read-only
  hashes/           Per-file SHA-256 + corpus fingerprint
  datasheet.md       Source, license, construction procedure, known limitations
scripts/            Deterministic build scripts for the policy corpus
  build_policy_corpus_v1.py
  freeze_and_hash.py
skill_library/      Distilled skills (precondition/action/postcondition) + dependency links
  v1/               131 frozen skills (115 policy-linked, 16 negative control), read-only
  audit/            20% link-quality audit: sample, two-annotator verdicts, kappa, report
  hashes/           Per-file SHA-256 + skill-library fingerprint
  dependency_links.json / .csv   Flat (skill_id, policy_id, policy_version, rule_ids) table
  CONSTRUCTION.md   Source, construction procedure, composition stats, known limitations
scripts/            (continued) extract_action_traces.py, distill_skills.py,
                    validate_skill_library.py, compute_audit_kappa.py,
                    apply_audit_exclusions.py, freeze_and_hash_skills.py,
                    select_supersessions.py, build_policy_corpus_v2.py,
                    build_environment_contract_anchor.py, label_ground_truth.py,
                    validate_phase3.py, freeze_and_hash_v2.py
policy_corpus/v2/   23 v2 policy documents (18 real-supersession, 5 cosmetic-only distractor)
ground_truth/       Ground-truth label table (Invalidated/Partial/Valid), supersession plan,
                    environment-drift sanity anchor, CONSTRUCTION.md
environment_contracts/  v1/v2 tool-argument schemas for the sanity-anchor drift case
preregistration/    Step 4 preregistration (procedures, metrics, thresholds), committed
                    before either detector existed
results/            Raw flag tables + execution logs for both conditions
  condition_a/      SKILLGUARD-style contract validation (incl. v1 calibration control)
  condition_b/      Dependency-link detector (section-level primary, document-level ablation)
  silent_wrong_action/  Replay logs + silent-wrong-action counts per condition
  hashes/           Step 4 fingerprint
  RUN_NOTES.md      What the numbers mean, isolation regime, findings, limitations
scripts/            (continued) run_condition_a.py, run_condition_b.py,
                    measure_silent_wrong_action.py, validate_step4.py,
                    test_leakage_check.py, freeze_and_hash_step4.py
  scoring/          Phase 5: main results table, Condition B error slice, ablations
  RESULTS.md        Phase 5 interpretation: verdict, error structure, ablations,
                    shared-gap placement, threats to validity
scripts/            (continued) score_conditions.py, slice_condition_b_errors.py,
                    run_ablations.py, freeze_and_hash_step5.py
```

## Getting the data

ABCD (Chen et al. 2021, [arXiv:2104.00783](https://arxiv.org/abs/2104.00783),
MIT license) is a third-party dataset, not something this repo produces, so
the large raw files are gitignored rather than vendored. The small manual and
taxonomy files this repo actually transforms into the policy corpus
(`data/guidelines.json`, `data/kb.json`, `data/ontology.json`, ~106KB total)
are tracked directly under `abcd-master/data/` for reproducibility.

To get the two large files this repo does NOT track
(`data/abcd_v1.1.json.gz`, `data/utterances.json`, needed from Phase 2
onward for skill distillation from actual dialogues):

```
# from the official ABCD repo
git clone https://github.com/asappresearch/abcd.git abcd-download
cp abcd-download/data/abcd_v1.1.json.gz abcd-download/data/utterances.json abcd-master/data/
```

Or download directly from the links in the
[ABCD README](https://github.com/asappresearch/abcd#usage).

## Progress

- [x] **Phase 1 — Versioned Policy Corpus.** ABCD's 55 agent-guideline
      subflows distilled into 37 intent-family policy documents (123 testable
      rules), hashed and frozen. Corpus fingerprint:
      `dd94cf1c9567fed864126bc48c7bd954e7643033037da4fff704d1b9b7441d87`. See
      `policy_corpus/datasheet.md` for full construction detail.
- [x] **Phase 2 — Skill distillation + dependency link recording.** 131
      skills distilled from ABCD action traces under the v1 policy corpus
      (115 policy-linked, 16 negative control = 12.2%); all 37 v1 policies
      have >=2 linked skills. 20% sample audited by two independent
      annotators, Cohen's kappa = 1.0 (threshold 0.8); both flagged the
      same 2 spurious skills, removed. Skill-library fingerprint:
      `4a1aea880cb1d5abafe40864a5919a4bf91b37ec5c3a92c3f1331ef5cc48e4e4`.
      See `skill_library/CONSTRUCTION.md` for full construction detail.
- [x] **Phase 3 — Inject supersessions (v2 policies) + ground truth
      labels.** 18 of 37 policies (48.6%) got a real-supersession v2 (20
      rule-level changes: 11 hard/always-flips, 9 value-dependent
      thresholds); 5 more got a cosmetic-only distractor v2; 14 stayed
      untouched. Ground truth across 115 linked skills: 40 invalidated /
      22 partial / 53 valid (class balance target was ~40/20/40 by
      count; found to be structurally unreachable jointly with the
      30-50%-of-policies target for this corpus's real skill density --
      resolved by prioritizing class balance, see
      `ground_truth/CONSTRUCTION.md`). One environment-drift sanity
      anchor (`select-faq` tool contract) added, isolated to 6 skills
      under two untouched policies. Phase 3 fingerprint:
      `dc164882823bde7c12f3e1bd20bd38f969b8dbeacd7fd25bfc3f157d1b281618`.
- [x] **Phase 4 — Run Condition A (SKILLGUARD baseline) vs. Condition B
      (dependency-link detector).** Preregistration committed before either
      detector existed. Condition A flags 6/131 — exactly the environment-drift
      sanity-anchor skills — with a v1 control flagging 0, evidencing the
      check-set is calibrated rather than weakened. Condition B (section-level)
      flags 76/131, including real precision loss on the planted cosmetic
      distractors, which is the measurement they were planted to produce.
      Silent wrong actions: **40/40 for Condition A, 0/40 for Condition B** —
      every invalidated skill the baseline missed replays cleanly against an
      unchanged environment while violating current policy. Isolation enforced
      mechanically (AST leakage check + its own negative test). Step 4
      fingerprint:
      `1924fd17d3d90aac9a6c71ef33cb3eceb7fa1f3deaccc43ec71118b61424a69c`.
      Scoring, CIs, error slices and ablations are Step 5 by design; see
      `results/RUN_NOTES.md`.
- [x] **Phase 5 — Results table, bootstrap CIs, error slices, ablations.**
      Scored both conditions against the frozen labels with bootstrap CIs
      (1000 resamples over skills, seed 20260820). **Verdict: HOLDS** against
      the preregistered threshold — invalidation recall 1.000 (B) vs 0.000 (A),
      silent wrong action rate 0.000 (B) vs 1.000 (A). Condition B precision
      0.526 primary / 0.816 partial-inclusive. Caveat recorded rather than
      buried: A's precision of 0.000 reflects that its 6 flags are *correct*
      environment-drift detections scored as non-positives by the invalidation
      labels, so the precision half of the test is satisfied trivially, not
      informatively. Condition B has **zero** false negatives; its error mass is
      entirely false-positive, dominated (61.1%) by the partial class.
      Ablations: link granularity shows **no** tradeoff on this corpus (identical
      flag sets, diagnosed); removing negative controls moves B's precision by
      **0.0 pts** (they are true negatives), with a link-free counterfactual
      detector supplied to demonstrate the inflation they actually guard against
      (+4.7 pts). Phase 5 fingerprint:
      `c09e79caeb22fcca5557a8e9a869c5ad04bbc745b32ff786b1b121ce50acd536`.
      See `results/RESULTS.md`.

## Experimental hygiene

- Every frozen artifact (policy corpora, skill library, ground-truth labels)
  is hashed the moment it's finalized and never edited in place afterward —
  changes become a new version.
- Condition B (the dependency-link detector) never reads the ground-truth
  label table; labels exist only for scoring, in an isolated pipeline.
- Random seeds fixed; every LLM call logged (model version, full prompt,
  full response).
- Any LLM-as-judge step is validated against 50 hand-labeled cases before
  being trusted at scale.

## License

`abcd-master/` retains ABCD's original MIT license (Chen et al. 2021,
ASAPP Research); large raw data files are gitignored, not vendored (see
"Getting the data" above). The policy corpus in `policy_corpus/` is a
derivative transformation of ABCD's guideline manual and inherits no
additional restriction; see `policy_corpus/datasheet.md` for details.
