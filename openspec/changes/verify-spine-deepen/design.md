# Design: verify-spine-deepen

## A — Gate signals

Base remains **stricter-of-two** (`passed < almost < owe_next`).

When base is `passed`, apply (in order):

| Condition | Effect | Signal code |
|-----------|--------|-------------|
| `score is not None` and `score < 0.4` | → `almost` | `low_score_blocks_pass` |
| else `evidence is not None` and `len(strip) < 8` | → `almost` | `empty_evidence_blocks_pass` |

- `None` means “not provided” → **no** downgrade (stubs / gold matrix unchanged).
- Score/evidence **never upgrade** a stricter base.
- `GateResult.signals: list[str]` appended; `reason` includes signal codes when set.
- Constants pinned in `core/loop.py` + `tests/test_gate_signals.py`.

## B — Harness surface

- `POST /v1/harness/runs` `{ case_set: "dev"|"gold", label? }` → `run_harness`
- `GET /v1/harness/runs?limit=`
- `GET /v1/harness/runs/{id}` + case results
- `PATCH /v1/harness/runs/{id}` `{ decision: adopt|observe|reject, note? }`

Decision stored in `summary.decision` / `decision_note` / `decided_at`
(no migration). Run `verdict` stays machine `pass|fail`.

No Settings tab — harness is a **dev/CI surface** (REST + CLI), not a learner
setting. Decision via `PATCH` remains the audit trail (P5 human judge); no auto
prompt register on adopt.

## C — ContextBudget

```text
ContextBudget(graph_max=600, lesson_max=600, total_max=900)
compose(budget_block, lesson_block) → ContextBlocks
```

When `len(graph)+len(lesson) > total_max`, trim **lessons first**, then
truncate graph. Priority inside graph stays depends → confuse → fail
(`format_budget_block`). Wired in `axiom.build_prompt`.
