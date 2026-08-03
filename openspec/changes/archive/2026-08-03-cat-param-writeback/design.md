# Design: cat-param-writeback

## Formula (pinned)

Binary ``y``: `passed`/`correct` → 1; `almost`/`owe_next`/`incorrect` → 0.

```text
n     = prior n_attempts on this claim
step  = 0.25 / √(n+1)

difficulty' = clip(difficulty + (1 − 2y) · step, 1, 5)
  # fail → harder; pass → easier

p0 = P(y=1 | θ=3, a, b)          # fixed reference ability
surprise = |y − p0|
a' = clip(a + 0.1 · (surprise − 0.25) / √(n+1), 0.05, 3.0)

n_attempts += 1
n_passed / n_failed accordingly
knowledge_key unchanged (still topic default when empty)
```

`normalize_calibration_meta` accepts float difficulty (round→int for
`CalibItem`); JSON may store continuous difficulty for gradual updates.

## Wire

| Path | When |
|------|------|
| `finalize_examine_with_gate` | after gate, before/after mastery writeback |
| `answer_calibration` | after binary outcome applied |

Return `calibration` dict snippet on writeback for traceability.
 No UI change.
