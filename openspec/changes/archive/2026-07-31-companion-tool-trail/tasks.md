# companion-tool-trail — tasks

## A — Backend open_examine on tool_calls

- [x] Extend `ToolCallRecord` / `record()` with optional `open_examine`
- [x] `start_examine` success path attaches payload (claim + note)
- [x] Orchestrator: optional message-level `metadata.open_examine` = last success
- [x] Tests: metadata shape + start_examine attach

## B — Web trail + CTA

- [x] Types: `CompanionToolCall` / `OpenExaminePayload` + helpers
- [x] `ChatPage/CompanionToolTrail` (quiet chips + 「开考」)
- [x] Wire under agent bubble; CTA → examine workflow
- [x] `startExamineNote` tolerates note missing from store (synthetic DayNote)

## C — Docs

- [x] `docs/SYSTEM.md` shipped + Not done
- [x] `openspec/changes/README.md` active / next candidates
- [x] README + README.zh-CN roadmap
