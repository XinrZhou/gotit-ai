# Implementation Review — Agent Runtime V2

> Engineering decision log for `openspec/changes/agent-runtime-v2/`.  
> Not a product backlog. Not a redesign of Verify Spine.  
> Date: 2026-08-03. Status: **Phase 0 done** (spec/ADR only); Phases 1–4 not shipped in code.

Normative specs: `openspec/changes/agent-runtime-v2/{proposal,design,tasks}.md`  
ADRs: `docs/adr/0003-learner-state-is-derived.md`, `docs/adr/0004-verify-run-envelope.md`  
Roadmap: `docs/agent-runtime-roadmap.md`

---

## 1. Why verify-first + thin envelope (not the original big Runtime)

Early V2 sketches described a full **Agent Runtime** unifying chat, examine,
teach, ingest under one `RunLifecycle`. Against the **actual** codebase that
was over-scoped:

| Fact in repo today | Implication |
|--------------------|-------------|
| Verify path already closes via `finalize_examine_with_gate` → `deterministic_gate` → `write_mastery_outcome` | Mastery floor exists; do not replace it |
| Chat is a separate `chat_orchestrator` + prepare-only tools | Unifying chat into the same lifecycle is a large rewrite with weak Week-1 payoff |
| `state-boundary-tighten` already enforced single mastery writer + prepare≠finalize | V2 should **stack contracts**, not reopen write planes |
| Harness `dev`/`gold` prove anti-corruption; no holdout suite / no agent-run replay | Highest leverage is **lock behavior before structure** |

**Adjusted plan (accepted):**

```text
Eval Replay + Holdout  →  LearnerStateSnapshot + EvidencePack (verify only)
  →  optional thin wrap of finalize (run_id / WriteIntent)
  →  later ToolSpec + Trace
```

**Rejected for this change:** day-one unified Runtime across all surfaces.

---

## 2. Current system positioning (honest)

| Claim | Status |
|-------|--------|
| Verification-centric **AI Agent Application** | **Shipped** — chat shell + fixed verify workflow |
| Personal Mastery **Agent Runtime** (unified run envelope, Snapshot type, EvidencePack, Replay) | **Target** — Phase 0 specs only; **not** implemented in `src/` yet |
| Multi-role agents (Axiom / Critic / Echo / Sage / Compass) | **Shipped** — role cast inside product workflows, not an open multi-agent platform |
| Deterministic mastery gate | **Shipped** — VISION P7; code in `core/loop.py` |
| Offline harness + human adopt\|observe\|reject | **Shipped** — audit only; **replay + holdout case sets now in CI** (`gate.sh`) |
| `SUITE_VERSION` on harness runs / adopt | **Shipped** (Phase 1) |

**One-line today:** Verification-centric Agent Application with a hard verify
spine. **One-line goal:** Personal Mastery Agent Runtime (engineering surface
on top of that spine).

Do **not** tell interviewers the Runtime envelope / Snapshot / Pack / Replay
already ship — they do not, until the matching Phase tasks are checked off.

---

## 3. Core architecture constraints (must not break)

| ID | Constraint |
|----|------------|
| C1 | `deterministic_gate` is the mastery judge — never an LLM |
| C2 | Mastery **row** writes only via `write_mastery_outcome` (verify through finalize; calibration/harness explicit `source`) |
| C3 | Companion tools: prepare ≠ mastery write |
| C4 | Drill / Sage do **not** pass the gate |
| C5 | `gotit.core` stays framework-free |
| C6 | REST ↔ MCP share `db.ops` / same finalize paths |
| C7 | Context on a budget (VISION P4); no default raw-note dump into verify prompts |
| C8 | `memory_entries` are not mastery authority |
| C9 | Adopt is audit-only; no auto prompt apply (VISION P5) |
| C10 | This change does **not** retune gate / schedule numeric formulas |

Source of freeze: ADR-0004 + `agent-runtime-v2` proposal Out.

---

## 4. Why we explicitly do **not** build these

### Unified mega-Runtime (chat + verify + ingest day one)

- Cost/risk dominate; chat is not the mastery write path.
- ADR-0004: wrap verify finalize; defer `chat_orchestrator` rewrite (Phases 1–3).

### Multi-Agent platform

- Product need is honest examine + companion, not open supervisor/worker collab.
- Five personas ≠ multi-agent OS; stacking orchestration dilutes Verified=done.

### Generic RAG / second brain

- Mastery is **claim/schedule/fail-graph state**, not retrieval hit rate.
- Optional claim-anchored retrieval (later, optional) must never write mastery
  alone. No vector store as authority.

### LearnerState as an authoritative table

- ADR-0003: Snapshot is a **derived projection** only.
- A writeable learner-profile table would become a second truth source next to
  `ClaimRow` / graph — consistency tax without AI-Eng upside.

---

## 5. Phase split and acceptance

| Phase | Goal | Acceptance (summary) | Code status |
|-------|------|----------------------|-------------|
| **0** | Spec + ADR lock | OpenSpec three files + ADR 0003/0004; Out explicit | **Done** |
| **1** | Replay + Holdout | ≥8 replay fixtures; holdout isolated; `gate.sh` wired; adopt↔`suite_version` | **Done** (2026-08-03) |
| **2** | Snapshot + EvidencePack | Builder + tests; verify callers use Pack only; chat behavior unchanged | Planned |
| **3** | Verify Run envelope | `run_id` / WriteIntent / idempotent commit around existing finalize | Optional stretch |
| **4** | Tool policy + Trace | Effect classes + read-only traces; short SYSTEM sync | After Week-1 |

Week-1 hard DoD (from Implementation Review): Phases **0 + 1 + 2**; Phase 3
nice-to-have; Phase 4 out of Week-1.

Full checklists: `openspec/changes/agent-runtime-v2/tasks.md`.

### Phase 1 completion notes (actual)

**Shipped in code:**

- `src/gotit/harness/cases/replay.py` — 9 cases through
  `finalize_examine_with_gate` / gate+commit / prepare-only / budget trim
- `src/gotit/harness/cases/holdout.py` — 5 cases; gate pairs disjoint from gold
- `scripts/run_replay_harness.py` + `run_harness.py --set replay|holdout`
- `scripts/gate.sh` runs replay then holdout (non-zero on fail)
- `SUITE_VERSION = 2026.08.03.agent-runtime-v2.phase1` stamped on every harness
  run summary; `set_harness_decision` always pins `suite_version` (optional
  override via API)

**Vs plan (honest deltas):**

| Plan item | Actual |
|-----------|--------|
| Critic downgrade via stub LLM | stub_critic **echoes** examine; downgrade case injects fixed recheck into the **same** `deterministic_gate` + `write_mastery_outcome` path finalize uses after Critic — not a live Critic call |
| Idempotent commit keys | Status stability under double finalize locked; **no** WriteIntent idempotency key yet (Phase 3) |
| EvidencePack / pack_hash | Out of Phase 1; trim case uses existing `compose_examine_context` |

**Unchanged:** gate thresholds, schedule formulas, chat orchestrator, web UI.

---

## 6. Coding bans (agents and humans)

While executing `agent-runtime-v2`:

1. Do not change gate / schedule **semantics or thresholds**.
2. Do not rewrite `chat_orchestrator` (Phases 1–3).
3. Do not ship web main-path / Done-bar / Brief product work in this change
   (owned by other OpenSpecs).
4. Do not add authoritative learner-profile tables or migrations that invent
   mastery truth.
5. Do not mount full gotit MCP into companion chat.
6. Do not auto-adopt prompts from harness decisions.
7. Do not open parallel finalize paths — wrap or call existing
   `finalize_examine_with_gate` / `finalize_claim_by_id`.
8. Do not expand into Multi-Agent platform, generic RAG, or multi-tenant auth.
9. One commit-sized story at a time; replay locks behavior before structural
   moves (Phase 1 before Phase 2/3).
10. Do not claim Runtime capabilities in `SYSTEM.md` until the matching Phase
    is actually merged.

---

## 7. Reality check vs related docs

| Doc | Role vs this file |
|-----|-------------------|
| `docs/v2_design.md` | Earlier design sketch; **execution authority** is OpenSpec + ADRs; this review records the **narrowing** |
| `docs/architecture_review.md` / `docs/project_analysis.md` | Analysis baselines; not task trackers |
| `docs/SYSTEM.md` | Onboarding snapshot — still describes shipped verify app; **should** list `agent-runtime-v2` as active eng wave when convenient (not required for Phase 0 code) |
| `docs/agent-runtime-roadmap.md` | Forward path; keep status labels in sync with `tasks.md` |

---

## 8. Code anchors (shipped today — do not mythologize)

| Concern | Path |
|---------|------|
| Gate / VerifyWorkflow | `src/gotit/core/loop.py` |
| Context budget (pre-Pack) | `src/gotit/core/context_budget.py` |
| Finalize | `src/gotit/api/verify_finalize.py` |
| Mastery writer | `src/gotit/db/ops/claim.py` → `write_mastery_outcome` |
| Companion prepare tools | `src/gotit/api/companion_tools.py` |
| Chat orchestrator | `src/gotit/api/chat_orchestrator.py` |
| Harness | `src/gotit/harness/`, `scripts/run_harness.py`, `scripts/gate.sh` |
