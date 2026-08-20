# Phase 5 Main Results

Population: 131 skills (40 invalidated, 22 partial, 69 valid). Bootstrap: 1000 resamples over skills, seed 20260820, percentile CIs.

## Primary (partial scored as a separate class)

| Condition | Invalidation recall | Invalidation precision | Silent wrong action rate |
|---|---|---|---|
| A (SKILLGUARD contract validation) | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] |
| B (dependency links, section-level) | 1.000 [1.000, 1.000] | 0.526 [0.405, 0.644] | 0.000 [0.000, 0.000] |

## Secondary (partial folded into the positive class)

| Condition | Recall | Precision | Silent wrong action rate |
|---|---|---|---|
| A (SKILLGUARD contract validation) | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] |
| B (dependency links, section-level) | 1.000 [1.000, 1.000] | 0.816 [0.725, 0.896] | 0.000 [0.000, 0.000] |

## Preregistered decision

- recall(B) = 1.000 vs recall(A) = 0.000 -> improved: True
- precision drop (A - B) = -52.6 pts (bound: 5.0) -> within bound: True
- **Verdict: HOLDS** -- Condition B improves invalidation recall over Condition A, and its precision does not drop more than the preregistered 5-point bound.

