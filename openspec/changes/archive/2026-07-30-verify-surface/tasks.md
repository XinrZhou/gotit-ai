# verify-surface — tasks

## Spec

- [x] proposal / design / tasks + HANDOFF prompts for tasks 2–3

## 1. Structured verify chips (this agent)

- [x] Shared `VerifyVerdict` chip component (quiet Apple)
- [x] ChatPage: show chip from `metadata.verdict` on examine agent turns
- [x] `useExamine` + `ChatTurn`/`ChatMsg` keep verdict; ChatLog renders chip
- [x] Touch `docs/SYSTEM.md` + `openspec/changes/README.md`

## 2. Critic independent model (other agent — see HANDOFF.md)

- [x] Bind Critic recheck to identity `llm_config` / env override
- [x] Tests: critic path uses distinct model when configured
- [x] SYSTEM note

## 3. Failure lessons → Axiom (other agent — see HANDOFF.md)

- [x] Budgeted inject of `failure_digest` into examine context
- [x] Prefer same claim / confuse neighbors; hard cap tokens
- [x] Tests + SYSTEM note
