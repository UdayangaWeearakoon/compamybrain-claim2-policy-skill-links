# Skill Library v1: Construction Notes

**Corpus version:** v1
**Frozen:** see `hashes/v1_checksums.json`
**Fingerprint (sha256 of sorted file hashes):** `4a1aea880cb1d5abafe40864a5919a4bf91b37ec5c3a92c3f1331ef5cc48e4e4`

Companion to `policy_corpus/datasheet.md` (Phase 1). This is not a
separately required deliverable per the execution guide, but is written
for the same reason: don't leave construction reasoning for the end.

## Source

ABCD dialogues (Chen et al. 2021, arXiv:2104.00783), train split
(`abcd-master/data/abcd_v1.1.json.gz`, 8,034 dialogues), plus the frozen
v1 policy corpus from Phase 1 (`policy_corpus/v1/`, fingerprint
`dd94cf1c9567fed864126bc48c7bd954e7643033037da4fff704d1b9b7441d87`).

## Construction procedure

1. **Extraction** (`scripts/extract_action_traces.py`, deterministic, no
   LLM): every train dialogue's gold action trace -- the ordered list of
   `(button, values)` pairs from every `speaker == "action"` turn -- was
   pulled out along with its scenario ground truth (subflow, flow,
   `personal.member_level`). 8,006 of 8,034 dialogues matched one of the
   55 subflows the v1 policy corpus covers; 28 (`status_questions`: 26,
   `status_delivery_date`: 2) carry a `scenario.subflow` value that exists
   in the released dialogue data but not in `guidelines.json` /
   `kb.json` / `ontology.json` -- the source material Phase 1 was built
   from. These 28 were set aside rather than distilled (no policy exists
   to link them to, and expanding the frozen Phase 1 corpus mid-Phase-2
   would violate hygiene rule #1). Separately, `status_active` (one of
   POL-032's three source subflows) has **zero** dialogues in any ABCD
   split (train, dev, or test) -- a data gap in the released corpus, not
   an extraction bug; POL-032 still has linked skills via its other two
   source subflows (`status_due_amount`, `status_due_date`).

2. **Clustering into skill variants** (`scripts/distill_skills.py`,
   deterministic): for each of the 37 v1 policies, dialogues from its
   source subflow(s) were grouped by the actual branch variable those
   rules key on. For the 13 tier-gated policies (>=1 rule names a
   membership tier), that's `member_level`, giving up to 4 branches (or 2,
   `{tier, non-tier}`, for the 2 policies whose rules single out only one
   tier). For the other 24 policies, dialogues were grouped by realized
   action-button signature instead (up to 3 variants), which surfaces
   other real branching (e.g. an Ask-the-Oracle Yes/No split) without
   membership tier as a factor. Each populated cluster becomes exactly one
   skill: `action_sequence` is the real, unmodified action trace from that
   cluster's most common signature; `rule_ids` are computed by scanning
   the policy's rule text for tier mentions (universal rules always
   included; tier-specific rules only for the matching branch) --
   code-derived, not memorized by hand.

3. **Negative controls** (16 skills, 12.2%): five hand-specified
   cross-cutting action patterns (universal account lookup, generic
   internal escalation, generic troubleshooting reflex, purchase
   validation as a bare gate, generic detail capture), each sub-clustered
   by a secondary key (e.g. flow, escalation target) and required to span
   >=2 distinct subflows before being accepted -- proof the pattern is
   genuinely cross-cutting, not a single-subflow artifact. Each carries
   `dependency_links: []`, `is_negative_control: true`, and real
   `provenance_convo_ids`.

4. **Manual review substitute.** Per-skill human review was replaced with
   an automated structural validator (`scripts/validate_skill_library.py`)
   -- unique skill_ids, every `rule_id` resolves in its policy, every
   `provenance_convo_id` is a real extracted dialogue, non-empty fields,
   no unfilled template placeholders. This is the same disclosed-limitation
   pattern as Phase 1's deterministic-template substitution for an LLM
   rewriting pass: stated explicitly rather than silently assumed away.

5. **20% audit.** Two independent LLM subagents (not human annotators --
   see `audit/kappa_report.md` for the same disclosure) reviewed a random
   20% sample (seed `20260819`) of the 117 originally-linked skills.
   Cohen's kappa = **1.0** (threshold: 0.8, passed). Both annotators
   independently flagged the same 2 skills as spurious; both were traced
   to a real root cause (see `audit/kappa_report.md`) and removed
   (`scripts/apply_audit_exclusions.py`), without renumbering any other
   skill_id.

## Final composition (post-audit)

- **131 total skills**: 115 policy-linked, 16 negative control (12.2%,
  within the 10-15% target band).
- All 37 v1 policies have >=2 linked skills (min 2, max 4 per policy).
- 115 linked skills collectively represent 4,170 real ABCD dialogues
  (the size of the clusters they were distilled from), not just the up-to-5
  convo_ids kept as inline provenance per skill.
- Tier-branch distribution among linked skills: gold 10, silver 8, bronze
  8, guest 8, non-gold 2 (the 2 single-tier policies).

## Known limitations

- **LLM-as-annotator, not human.** Both the "manual review" (Phase 2 step
  4 above) and the "two annotators" (step 5) are automated/LLM
  substitutes for what the execution guide specifies as human review. This
  mirrors Phase 1's disclosed LLM-substitution choice and is flagged for
  the same reason: a future pass with real human reviewers could produce
  different kappa or catch different spurious links.
- **Representative-dialogue selection can occasionally mismatch.** The
  clustering step's "most frequent action signature" heuristic picked a
  real-but-off-policy dialogue pattern as a cluster's representative twice
  in the audited 20% sample (see `audit/kappa_report.md`); a mechanical
  attempt to generalize that check to the full 117 produced 47 flags, the
  large majority false positives (legitimate early exits / denials /
  skipped optional steps). The true error rate among the *un-audited* 80%
  of skills is therefore unknown beyond what the audited sample suggests
  (2/23 in-sample, before exclusion) -- a full audit of the remaining
  skills was out of scope for Phase 2 but is a natural Phase 3+ check if
  results look sensitive to it.
- **member_level is a scenario label, not a causal guarantee.** Clustering
  by `scenario.personal.member_level` assumes the real dialogue's action
  trace actually reflects that tier's treatment per the Phase 1 rules;
  spot checks (e.g. POL-004 in the audit sample) confirm this, but it was
  not exhaustively verified skill-by-skill.
- **Real dialogues sometimes deviate from the documented guideline order**
  (see SK-053's root cause in the audit report) -- ABCD's human agents did
  not always follow the written manual exactly, which is realistic but
  means "distilled from real dialogues" is not the same guarantee as
  "distilled from guideline-compliant dialogues."
