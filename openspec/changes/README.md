# Active OpenSpec changes

One folder per change (`proposal.md`, `design.md`, `tasks.md`, optional `specs/`).
Archive with a date stamp when done.

## Prefer merge over new folders

Before creating `openspec/changes/<new-name>/`, list active siblings (not
`archive/`) and ask: same subdomain, same UI surface, or follow-up of an open
proposal? If yes → fold into that change and delete the duplicate folder.

## Current active

| Change | Notes |
|--------|-------|
| `verify-spine-deepen/` | Gate signals + ContextBudget + Harness REST/CLI |
| `note-ingest-next-step/` | Note ingest → ready card → 去开考 |
| `daily-brief-polish/` | Daily brief UI polish (may be ship-ready) |
| `yuque-md-convert-wipe/` | Yuque md convert (may be ship-ready) |

## Recently archived

| Archive | Notes |
|---------|-------|
| `archive/2026-07-31-day-close-ritual/` | Today close ritual + companion `close_day` |
| `archive/2026-07-31-digest-to-claim/` | Interest → promotable claims → plan |
| `archive/2026-07-31-chat-action-blocks/` | `metadata.action_blocks` + Chat ActionBlocks |
| `archive/2026-07-31-first-pass-bootcamp/` | Empty-library first-pass guide |
| `archive/2026-07-31-voice-teachback-verify/` | Voice/text teach-back via shared finalize |
| `archive/2026-07-31-explainable-schedule/` | due_reason templates + `depends_on` |
| `archive/2026-07-31-interview-learning-arc/` | Today `interview_focus` deep-drill hint |
| `archive/2026-07-31-ramp-open-drill/` | Companion `start_drill` + bubble「深挖」 |
| `archive/2026-07-31-interview-countdown-ramp/` | Deterministic ramp tiers + nudges |
| `archive/2026-07-31-companion-tool-trail/` | Quiet tool trail + one-tap examine |
| `archive/2026-07-31-mcp-verify-finalize-parity/` | Shared verify finalize REST↔MCP |
| `archive/2026-07-30-cold-start-calibration/` | CAT-lite cold start |
| `archive/2026-07-30-digest-evening-wrap/` | Evening wrap + news separate |
| `archive/2026-07-30-companion-tools-and-schedule/` | Builtin tools + spaced schedule |

Also archived 2026-07-30: `chat-shell`, `chat-plan-context`, `mastery-graph`,
`notes-batch-delete`, `profile-center`, `resume-import`, `workflow-in-thread`,
`companion-os`, `verify-surface`, `daily-verify-loop`, `composer-at-mention`
→ `openspec/changes/archive/2026-07-30-*`.

## Later (not opened yet)

- Auto prompt/skill register on harness adopt
- Broad per-agent multi-model beyond Critic
- Broad agent-as-tool against full MCP catalog
