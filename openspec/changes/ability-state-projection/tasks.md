# Tasks: ability-state-projection

## OpenSpec

- [x] proposal / design / tasks landed

## P0-1 / P0-2

- [x] Ability projection + next_action + surfaces + tests

## P0-3 Chat state context

- [x] `core/companion_state_context.py` — format + growth goal + guardrail
- [x] `db.ops.build_companion_state_brief`
- [x] `build_chat_prompt` / `run_chat` / `chat_orchestrator` inject read-only brief
- [x] Tests: brief sections + prompt guardrail
- [x] SYSTEM one-liner

## Verify

- [x] `uv run pytest tests/test_ability_projection.py tests/test_next_action.py tests/test_companion_state_context.py tests/test_chat_plan_context.py -q`
