# Tasks: agent-runtime-v2

> 验收：`proposal.md` Success + Implementation Review Week-1 DoD。  
> 禁止：改 gate/schedule 公式、web 产品、chat 大一统、权威 Learner 表。  
> 顺序：先 Phase 1 锁行为，再 Phase 2 挪，再可选 Phase 3 信封。

## Phase 0 — Spec lock

- [x] `proposal.md` / `design.md` / `tasks.md` landed
- [x] ADR-0003 LearnerStateSnapshot is derived-only
- [x] ADR-0004 Verify Run envelope; gate stays code; chat deferred
- [x] Out / Success / module forbid list explicit (no business code in Phase 0)

## Phase 1 — Eval Replay + Holdout

- [x] Add harness case_set `holdout` isolated from `dev`/`gold`
- [x] `scripts/run_replay_harness.py`: stub/fixture → assert gate/writeback contracts
- [x] ≥8 replay fixtures (downgrade, empty evidence, prepare-only no mastery,
      trim/pack signals, teach mapping, idempotency-ready hooks, …)
- [x] Wire replay (+ holdout) into `scripts/gate.sh`
- [x] Bind harness adopt decision to `suite_version`
- [x] `./scripts/gate.sh` green with new suites

## Phase 2 — LearnerStateSnapshot + EvidencePack

- [x] `core/learner_state.py`: `LearnerStateSnapshot` + `build_learner_state`
- [x] Unit tests: mastery/owed/fingerprint change without LLM
- [x] Extend `context_budget` → `EvidencePack` + `build_evidence_pack` + `pack_hash`
- [x] Migrate verify callers only: `verify_attempt`, examine/teach routes, MCP
      examine/teach — no hand-rolled graph/lesson join
- [x] Replay asserts `pack_hash_stable` / trim-class signals where applicable
- [x] Chat orchestrator **unchanged** behavior

## Phase 3 — Verify Run envelope (optional Week-1 stretch)

- [x] `core/agent_run.py`: `AgentRun` / `WriteIntent` / `CommitReceipt` types
- [x] Wrap `finalize_examine_with_gate`: propose → evaluate → commit
- [x] Persist `run_id` on mastery-related audit; idempotent commit key
- [x] Replay asserts WriteIntent ↔ GateResult ↔ DB effect
- [x] Do **not** unify `chat_orchestrator`

## Phase 4 — Tool / Obs (after Week-1; same change folder OK)

- [ ] `ToolSpec.side_effect` registry; contract test: chat forbids
      `write_authoritative`
- [ ] AgentTrace store + CLI or read-only `GET /v1/obs/runs/{id}` (no product UI)
- [ ] Short `docs/SYSTEM.md` sync (Runtime envelope + Pack + Replay)

## Docs / gate (ongoing)

- [x] Phase 1–3 complete → `docs/SYSTEM.md` 已同步 Runtime V2 / Snapshot / Pack / 信封
- [x] 收敛文档中文化并纠偏：`ai-engineering-story` / roadmap / implementation-review /
      architecture_review / project_analysis；`v2_design` 标明草图地位
- [ ] Archive this change when Phases 1–3 accepted — before mega-commit;
      prefer split commits per Implementation Review

## Out / never in this change

- [ ] ~~Rewrite chat RunLifecycle~~
- [ ] ~~Generic RAG / learner authoritative table~~
- [ ] ~~Auto-adopt prompts / Multi-Agent platform~~
- [ ] ~~Web main-path / Done-bar work~~
