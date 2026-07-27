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
   - `gotit_fill_today_from_queue` — pull due / not-yet claims into today's plan
   - `gotit_list_notes` / `gotit_add_note` / `gotit_ingest_note`
   - `gotit_ingest` — extract claims from raw material
   - `gotit_examine` — run a check mode on a claim (stub; pass `passed` for writeback)
2. Do **not** mark mastery from confidence. Wait for check evidence.
3. On fail: coach the failed slice only, then re-examine.
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
