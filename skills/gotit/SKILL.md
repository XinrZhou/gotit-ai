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
   - `gotit_get_plan` / `gotit_upsert_plan_item` / `gotit_update_plan_item`
   - `gotit_fill_today_from_queue` — pull due / not-yet / in-progress claims into today
   - `gotit_list_notes` / `gotit_add_note` / `gotit_ingest_note`
   - `gotit_ingest` — extract claims from raw material
   - `gotit_examine` — multi-turn examination by **Axiom**; pass `answer` + `history`,
     returns `{done, verdict, follow_up}`; writeback on `done=true`. Pass `verdict`
     directly (passed|almost|owe_next) to bypass the agent (stub/tests).
   - `gotit_teach` — teach-back mode by **Echo**; pass `topic` + `answer` + `history`,
     returns `{done, you_taught_well, gaps, next_question}`.
   - `gotit_curate` — add recommended claims (by text) to a day's plan (**Compass**)
   - `gotit_list_memory` / `gotit_add_memory` — layered memory (long/working/session)
   - `gotit_list_prompts` / `gotit_register_prompts` — prompt version observation
   - `gotit_upload_resume` — upload a resume file (local path), extract + parse to a
     `ResumeDocument{basics, projects[]}`; returns `{upload_id, document}`
   - `gotit_apply_resume` — apply an (edited) parsed resume: **clear-rebuilds** the project
     library + one resume-note per project (default no ingest); user hand-written notes/claims
     are preserved (project_id detached)
   - `gotit_get_resume` — current global resume record (or null)
   - `gotit_list_drill_materials` / `gotit_upsert_drill_material` / `gotit_delete_drill_material`
     — user-imported deep-dive materials, consumed by the interviewer as context
   - `gotit_start_drill_session` — start a resume-driven mock interview by **Sage** (桑迪);
     pass `round` (tech_1|tech_2|tech_3|tech_4|hr) + optional `direction` (e.g. "偏架构") +
     optional `project_id` (focus one project); returns `{session, verdict}`
   - `gotit_continue_drill_session` — continue a session with the candidate's `answer`;
     returns `{verdict}`; session auto-finishes when `done=true`
   - `gotit_list_drill_sessions` / `gotit_get_drill_session` — session history (persisted)
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
