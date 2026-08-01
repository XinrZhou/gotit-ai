# Tasks: verify-spine-deepen

## 1. Gate signals

- [x] Extend `GateResult` with `signals`
- [x] Implement score/evidence downgrade rules in `deterministic_gate`
- [x] `tests/test_gate_signals.py` + extend `gate-no-llm` harness case lightly

## 2. ContextBudget

- [x] Add `core/context_budget.py` + compose/trim
- [x] Wire `axiom.build_prompt`
- [x] `tests/test_context_budget.py`

## 3. Harness surface

- [x] `db.ops`: `get_harness_run`, `set_harness_decision`
- [x] REST `/v1/harness/*`
- [x] `tests/test_harness_api.py`
- [x] Settings Harness UI removed (wrong surface; keep REST/CLI only)

## 4. Docs

- [x] Update `docs/SYSTEM.md` (gate signals, ContextBudget, harness UI)
- [x] Check off tasks when done
