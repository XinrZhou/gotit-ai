# ADR-0003: LearnerStateSnapshot is derived-only

- Status: Accepted
- Date: 2026-08-03
- OpenSpec: `openspec/changes/agent-runtime-v2/`

## Context

Long-term learner truth already lives on **claims** (mastery / schedule),
**fail_events** / **graph_edges** (failure structure), and derived caches such
as **failure_digest**. Chat `memory_entries` and thread messages are not the
mastery authority (`state-boundary-tighten`, VISION P1/P2).

V2 work needs a single, explainable **read model** for “why owed / where weak /
what lessons to inject” so agents and eval fixtures do not re-assemble ad-hoc
SQL in every caller. The risk is inventing a second writeable “learner profile”
table that drifts from claim/graph truth.

## Decision

1. Introduce **`LearnerStateSnapshot`** as a **derived, versionable projection**
   built in `gotit.core` from authoritative (and approved derived-cache) rows.
2. **Do not** add an authoritative DB table whose rows define mastery, owed, or
   skill state independently of `ClaimRow` / graph / schedule writers.
3. Agents and EvidencePack **consume** the snapshot (plus per-claim blocks);
   they must not treat chat prose or raw `memory_entries` as mastery truth.
4. Rebuild on read (or invalidate via fingerprint); never “patch” the snapshot
   as if it were source-of-truth state.

## Alternatives considered

- New `learner_profiles` (or similar) authoritative table: rejected — second
  truth source; migration and consistency cost without AI-Eng upside.
- Chat-history-as-memory only: rejected — fails cross-day mastery narrative and
  contradicts existing write planes.
- Embedding / skill-vector store as mastery memory: rejected for this change —
  mastery is schedulable claim state, not retrieval hit rate.

## Consequences

- Phase 2 implements `build_learner_state` + tests without schema migrations.
- Brief / verify context / replay fixtures should converge on the same builder.
- Digests and Brief aggregates remain **derived**; `write_mastery_outcome` and
  graph/fail writers remain the only mastery-related authority paths.
- Interview story: Memory Architecture = taxonomy + projection, not “we added
  a vector DB.”
