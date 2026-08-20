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
                    apply_audit_exclusions.py, freeze_and_hash_skills.py
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
- [ ] Phase 3 — Inject supersessions (v2 policies) + ground truth labels
- [ ] Phase 4 — Run Condition A (SKILLGUARD baseline) vs. Condition B
      (dependency-link detector)
- [ ] Phase 5 — Results table, bootstrap CIs, error slices, ablations

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
