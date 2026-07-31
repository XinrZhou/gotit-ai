---
name: gotit
description: >-
  Verify whether the user actually learned material (false fluency checks).
  Use when the user pastes notes and wants to prove mastery — probes, drills,
  coaching gaps, mastery gates. Also use for daily learning plans and notes.
  Calls gotit-ai MCP tools; does not summarize-only.
---

# gotit — learning verification

When the user wants to **check understanding** (not just summarize):

1. Prefer MCP tools from the `gotit` server:
   - `gotit_health` — connectivity
   - `gotit_today` — today's plan + truncated notes + due claims
   - `gotit_get_plan` / `gotit_upsert_plan_item` / `gotit_update_plan_item` / `gotit_delete_plan_item`
     （计划 CRUD；`due_time=HH:MM`；upsert/delete 会自动同步提醒事项）
   - `gotit_fill_today_from_queue` — pull due / not-yet / in-progress claims into today
   - `gotit_list_notes` / `gotit_add_note` / `gotit_ingest_note`
   - `gotit_ingest` — extract claims from raw material
   - `gotit_examine` — multi-turn examination by **Axiom**; pass `answer` + `history`,
     returns `{done, verdict, follow_up}`; writeback on `done=true`. Pass `verdict`
     directly (passed|almost|owe_next) to bypass the agent (stub/tests). Optional
     `thread_id` appends turns into a companion thread stream.
   - `gotit_teach` — teach-back mode by **Echo**; pass `topic` + `answer` + `history`,
     returns `{done, you_taught_well, gaps, next_question}`. Optional `thread_id`
     likewise.
   - `gotit_curate` — add recommended claims (by text) to a day's plan (**Compass**)
   - `gotit_list_memory` / `gotit_add_memory` — layered memory (long/working/session)
   - `gotit_list_prompts` / `gotit_register_prompts` — prompt version observation
   - `gotit_upload_resume` — upload a resume file (local path), extract + parse to a
     `ResumeDocument{basics, projects[]}`; returns `{upload_id, document}`
   - `gotit_apply_resume` — apply an (edited) parsed resume: **clear-rebuilds** the
     project library from resume projects (no quiz notes; Sage consumes the resume
     document during 深挖); user hand-written notes/claims
     are preserved (project_id detached)
   - `gotit_get_resume` — current global resume record (or null)
   - `gotit_list_drill_materials` / `gotit_upsert_drill_material` / `gotit_delete_drill_material`
     — user-imported deep-dive materials, consumed by the interviewer as context
   - `gotit_start_drill_session` — start a resume-driven mock interview by **Sage** (桑迪);
     pass `round` (tech_1|tech_2|tech_3|tech_4|hr) + optional `direction` (e.g. "偏架构") +
     optional `project_id` (focus one project) + optional `thread_id`; returns `{session, verdict}`
   - `gotit_continue_drill_session` — continue a session with the candidate's `answer`
     (+ optional `thread_id`); returns `{verdict}`; session auto-finishes when `done=true`
   - `gotit_list_drill_sessions` / `gotit_get_drill_session` — session history (persisted)
   - `gotit_list_interviews` / `gotit_upsert_interview` / `gotit_update_interview_status`
     — scheduled real-world interviews (company, role, time, round)
   - `gotit_list_due_interview_reminders` / `gotit_mark_interview_reminded`
     — cron due list + dedup writeback for OpenClaw interview-remind skill
2. Do **not** mark mastery from confidence. Wait for check evidence.
3. On `almost`: keep the claim in today's queue (in_progress); on `owe_next`: re-queue
   for another day; only `passed` advances to mastered.
4. Keep context small: prefer `gotit_today` / note excerpts over dumping full notebooks.
5. Plans are verification queues, not habit trackers — completion = check evidence.

## OpenClaw MCP config (example)

```json
{
  "mcp": {
    "servers": {
      "gotit": {
        "command": "uv",
        "args": ["run", "--directory", "/absolute/path/to/gotit-ai", "gotit-mcp"]
      }
    }
  }
}
```

For remote HTTP MCP (when streamable-http is enabled on the API), use `url` + `transport: "streamable-http"` and `Authorization: Bearer <GOTIT_API_KEY>`.

## WeChat channel (P0)

Channels live on **OpenClaw**, not inside gotit. For WeChat (Tencent
`@tencent-weixin/openclaw-weixin`) + this MCP server:

1. Follow **[docs/openclaw-wechat.md](../../docs/openclaw-wechat.md)** (Node 22+,
   plugin install, QR login, MCP path).
2. Acceptance: WeChat DM can drive `gotit_health` and `gotit_today`.
3. Do **not** add Feishu/WeChat adapters under `src/gotit/`.

## Digests (P1c)

Morning = today's plan; evening = today wrap + tomorrow plan Q&A
(never mixes news or 今日待检). Optional separate `news` RSS job.
Skill: `skills/digest/`.
See **[docs/openclaw-digest.md](../../docs/openclaw-digest.md)**.

## Apple plan bridge (P1d)

Import Reminders / Notes into gotit plan via **`skills/apple-plan/`**
(osascript on Mac). See **[docs/openclaw-apple-plan.md](../../docs/openclaw-apple-plan.md)**.
Do **not** call Apple APIs from gotit core.

## Interviews (P3d + P4 ramp)

- `gotit_list_interviews` / `gotit_upsert_interview` / `gotit_update_interview_status`
- `gotit_list_due_interview_reminders` / `gotit_mark_interview_reminded`
- Upcoming + ramp: `gotit_list_upcoming_interviews` /
  `gotit_list_interview_ramp_nudges` / `gotit_mark_interview_ramp_nudged` /
  `gotit_get_interview_ramp_prefs` / `gotit_put_interview_ramp_prefs`
- Delivery skill: `skills/interview-remind/`（offset + ramp 同 cron）

## Failure digest (P3b)

Examine `almost`/`owe_next` queues `failure_digest` memory (deduped per claim+verdict).
- `gotit_list_pending_failure_digests` / `gotit_mark_failure_digest_notified`
- Delivery: `skills/failure-digest/`

## Voice teach / coding (P3c / P2)

- `skills/voice-teach/` — WeChat voice → ASR (OpenClaw) → `gotit_teach`
- `skills/coding/` — allowlisted workspace coding from WeChat

Shell writeback / obs (bridge):

- `gotit_record_shell_event` / `gotit_record_interest`
- `gotit_list_shell_activity` / `gotit_obs_profile` / `gotit_obs_graph`
