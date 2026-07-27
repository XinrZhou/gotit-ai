---
name: gotit
description: >-
  Verify whether the user actually learned material (false fluency checks).
  Use when the user pastes notes and wants to prove mastery — probes, drills,
  coaching gaps, mastery gates. Calls gotit-ai MCP tools; does not summarize-only.
---

# gotit — learning verification

When the user wants to **check understanding** (not just summarize):

1. Prefer MCP tools from the `gotit` server:
   - `gotit_health` — connectivity
   - `gotit_ingest` — extract claims from material
   - `gotit_examine` — run a check mode on a claim
2. Do **not** mark mastery from confidence. Wait for check evidence.
3. On fail: coach the failed slice only, then re-examine.
4. Keep context small: inject the claim under test, not the whole notebook.

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
