# Active OpenSpec changes

One folder per change (`proposal.md`, `design.md`, `tasks.md`, optional `specs/`).
Archive with a date stamp when done.

## Prefer merge over new folders

Before creating `openspec/changes/<new-name>/`, list active siblings (not
`archive/`) and ask: same subdomain, same UI surface, or follow-up of an open
proposal? If yes → fold into that change and delete the duplicate folder.

Current active: **`verify-surface`**（结构化判定 UI；Critic 独立模型 / failure
注入见该目录 `HANDOFF.md`）。

Archived 2026-07-30: `chat-shell`, `chat-plan-context`, `mastery-graph`,
`notes-batch-delete`, `profile-center`, `resume-import`, `workflow-in-thread`,
`companion-os` → `openspec/changes/archive/2026-07-30-*`.

Next candidates (not opened yet): chat local agent-tools（改计划 / 开考）、
interview countdown ramp（P4）.
