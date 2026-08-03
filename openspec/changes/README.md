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
| **`apple-interview-calendar/`** | 面试安排自动同步 Mac 日历「面试」 |
| **`settings-ia-shell-activity/`** | Settings 我/提醒/高级；动态顶栏 + 删除 API |
| **`main-path-converge/`** | 产品故事 S1–S8：空态/深挖诚实/过关可感（UX 作者自管；近归档） |
| **`mastery-graph-deepen/`** | 弱点图谱：开练用法 + 跨主题/近14天结构（非百科 KG） |

## Recently archived

| Archive | Notes |
|---------|-------|
| `archive/2026-08-03-eval-harness-loop/` | Harness metric rollups + deeper offline cases |
| `archive/2026-08-03-failure-writeback-regress/` | Failure digest → re-examine inject + schedule table |
| `archive/2026-08-03-verify-spine-deepen/` | Gate signals + ContextBudget + Harness API/CLI |
| `archive/2026-08-03-form-follows-claim/` | `preferred_check_mode` CTA routing |
| `archive/2026-08-03-cat-param-writeback/` | Item-param writeback on gate / calib |
| `archive/2026-08-03-note-ingest-next-step/` | 出题 → 去开考 |
| `archive/2026-08-03-daily-brief-polish/` | DailyBrief UI（手测并入主路径走查） |
| `archive/2026-08-03-yuque-md-convert-wipe/` | Yuque editor convert wipe fix |
| `archive/2026-08-03-mcp-split-stack-honest/` | MCP package split + stack honesty |
| `archive/2026-08-03-legacy-surface-cleanup/` | Drop chat_messages / VerifyLoop / Redis |
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

- Drill mastery honesty: keep prep-only copy **or** wire claim-close finalize
- Full APPLY verify form (today → probe)
- Auto prompt/skill register on harness adopt（仍禁止；审计 only）
- Broad per-agent multi-model beyond Critic
- ~~Broad agent-as-tool against full MCP catalog~~ — **not near-term** (whitelist stays)
- ~~Mastery-graph deepen~~ → opened as `mastery-graph-deepen/`
