# Agent Runtime Roadmap

> From **Verification-centric AI Agent Application** (today) toward  
> **Personal Mastery Agent Runtime** (engineering target).  
> Tracked change: `openspec/changes/agent-runtime-v2/`.  
> Companion review: `docs/implementation-review.md`.  
> Last updated: 2026-08-03.

Status legend:

| Label | Meaning |
|-------|---------|
| **已实现** | In `src/` / CI today; safe to claim in interviews as shipped |
| **实施中** | Spec accepted; implementation in progress or next |
| **未来规划** | In-scope for this roadmap, not started |
| **明确不做** | Rejected for this trajectory (see review / ADRs) |

---

## Current state — 已实现

**Verification-centric AI Agent Application**

```text
Chat / MCP surfaces
  → role agents (examine / teach / drill / chat tools)
  → Critic + deterministic_gate
  → write_mastery_outcome (+ trajectory / fail graph)
```

Already true in code (non-exhaustive; see `docs/SYSTEM.md`):

- Fixed Verify Spine; gate is code (VISION P7)
- Single mastery row writer; prepare ≠ finalize (`state-boundary-tighten`)
- REST ↔ MCP share domain ops
- `ContextBudget` / `compose_examine_context` for examine (not yet EvidencePack)
- Offline harness `dev`/`gold` + human adopt\|observe\|reject (audit)
- Companion tool whitelist (prepare-only open_* CTAs)
- Drill does not pass the gate

**Not true yet (do not overclaim):**

- No `LearnerStateSnapshot` type/builder in `src/`
- No `EvidencePack` / `pack_hash`
- No verify `AgentRun` / `WriteIntent` envelope / mastery `run_id` contract
- Chat and verify are still **two** orchestration paths

**Phase 1 now true:**

- Replay suite (`case_set=replay`) + holdout suite (`case_set=holdout`)
- `scripts/run_replay_harness.py`; both wired in `scripts/gate.sh`
- Harness summary / adopt carries `suite_version`

---

## Target state — 未来目标（工程）

**Personal Mastery Agent Runtime**

```text
Verify surfaces
  → LearnerStateSnapshot (derived) + EvidencePack
  → thin Run envelope: propose → evaluate → commit
  → Replay + Holdout guardrails
  → (later) ToolSpec policy + read-only traces
```

Chat remains a first-class **product** surface; it is **not** required to share
the full RunLifecycle for the target to be interview-credible. Mastery truth
stays on claims/graph/schedule.

---

## Evolution phases

### Phase 0 — Spec / ADR

| | |
|--|--|
| **Status** | **已实现**（文档） |
| **目标** | Freeze Out, success criteria, ADRs before code |
| **技术价值** | Prevents scope bleed into UX / mega-Runtime |
| **面试价值** | Shows judgment: Runtime as envelope, not buzzword rewrite |
| **明确不做** | Business code; redesigning gate; claiming Runtime shipped |

Delivered:

- `openspec/changes/agent-runtime-v2/{proposal,design,tasks}.md`
- `docs/adr/0003-learner-state-is-derived.md`
- `docs/adr/0004-verify-run-envelope.md`

---

### Phase 1 — Replay + Holdout Evaluation

| | |
|--|--|
| **Status** | **Completed** (2026-08-03) |
| **目标** | Lock verify/gate/writeback contracts without live LLM; isolate holdout |
| **技术价值** | Regression net before Pack/envelope moves; VISION P5 teeth |
| **面试价值** | “How do you know a prompt/budget change didn’t regress?” |
| **明确不做** | Holdout product UI; auto-adopt; retuning gate thresholds to make cases pass |

**Actual implementation:**

- Replay: 9 cases in `harness/cases/replay.py` (pass write, critic-stricter
  commit path, empty evidence, prepare-only, stub pollution, context trim,
  double-finalize status stability, entry parity incl. teach map, low score)
- Holdout: 5 cases in `harness/cases/holdout.py` (disjoint gate pairs, score/
  evidence finalize, stricter recheck write, teach mapping, isolation guard)
- Runner: `scripts/run_replay_harness.py`; also `--set` on `run_harness.py`
- CI: `gate.sh` runs replay + holdout after dev harness
- Version pin: `gotit.harness.SUITE_VERSION`; adopt always records it

**Vs plan:**

- Critic downgrade uses fixed recheck → shared gate+write path (stub Critic
  cannot diverge by design)
- Idempotency = status stability under repeat finalize; WriteIntent keys wait
  for Phase 3
- No EvidencePack yet (Phase 2)

---

### Phase 2 — LearnerStateSnapshot + EvidencePack

| | |
|--|--|
| **Status** | **实施中**（next code phase; after Phase 1 Completed） |
| **目标** | Derived learner projection + budgeted context compiler on **verify** path |
| **技术价值** | Memory taxonomy without second truth; kill duplicated examine context assembly |
| **面试价值** | Memory Architecture + Context Engineering with code anchors |
| **明确不做** | Authoritative learner table; forcing chat to consume Pack; generic RAG |

Builds on existing `context_budget.py` and claim/graph/digest readers — extend,
do not replace authority.

---

### Phase 3 — Verify Run Envelope

| | |
|--|--|
| **Status** | **未来规划**（optional Week-1 stretch） |
| **目标** | Thin wrap of `finalize_examine_with_gate`: WriteIntent / `run_id` / idempotent commit |
| **技术价值** | Explicit propose→evaluate→commit; auditable mastery writes |
| **面试价值** | “Production agent = state machine with commit boundary” |
| **明确不做** | Unified chat+verify+ingest Runtime; parallel second finalize service |

Week-1 may ship without Phase 3; interview minimum remains Spine + Snapshot +
Pack + Replay once Phases 1–2 land.

---

### Phase 4 — Tool Policy + Trace

| | |
|--|--|
| **Status** | **未来规划**（after Week-1 DoD） |
| **目标** | `ToolSpec` side-effect classes; read-only run traces; short SYSTEM sync |
| **技术价值** | Policy-as-code for tools; debug model vs tool vs gate |
| **面试价值** | Tool governance + observability without monitoring-product theater |
| **明确不做** | Full MCP-in-chat; fancy ops dashboards; changing prepare≠finalize |

---

## Cross-cutting: 明确不做（整条路线）

| Item | Why |
|------|-----|
| Mega unified Runtime day one | ADR-0004; cost/risk |
| Multi-Agent collaboration platform | Dilutes Verified=done |
| Generic RAG / second brain | Mastery ≠ retrieval |
| LearnerState authoritative table | ADR-0003 |
| LLM-as-gate / auto-adopt | VISION P7 / P5 |
| Drill过门 | Product iron law |
| Web main-path work inside this change | Other OpenSpecs own UX |
| Gate/schedule formula retune | Frozen for this change |

---

## Suggested reading order

1. `docs/SYSTEM.md` — what ships for learners today  
2. This roadmap — where eng is going  
3. `docs/implementation-review.md` — why the plan was narrowed  
4. `openspec/changes/agent-runtime-v2/` — executable tasks  
5. ADR-0003 / ADR-0004 — non-negotiable decisions  

When a Phase merges, update: `tasks.md` checkboxes → this file status labels →
`docs/SYSTEM.md` only if onboarding/architecture story drifts.
