# Design: mcp-split-stack-honest

## MCP layout

```
mcp/
  app.py           # FastMCP("gotit") singleton
  common.py        # _user_id, _verify_meta, _finalize_claim_mcp
  tools/
    __init__.py    # import submodules → register @mcp.tool
    health.py
    day.py
    notes.py
    examine.py     # ingest stub + examine + start_verify
    teach.py
    memory.py
    shell.py       # shell + obs profile/graph
    graph.py       # depends_on
    prompts.py
    projects.py
    resume.py
    drill.py
    interviews.py
    thread.py      # threads + post_message + seed identities
    skills.py
    connectors.py
    calibration.py
  server.py        # import tools; main(); re-export tools for tests
```

Registration = import side effects on the shared `mcp` instance (same as
today). No tool logic rewrite; REST↔MCP parity unchanged.

## Stack honesty (personal use)

- Default: one learner (`GOTIT_USER_ID`), bearer `GOTIT_API_KEY`.
- Redis: keep Compose service for local convenience; docs + `.env.example`
  say **unused by application code**.
- Verify: agents/docs point at `deterministic_gate` /
  `finalize_examine_with_gate`; `VerifyLoop` = legacy in-memory skeleton
  (tests may still use it).

## Dual messages

| Table | Role |
|-------|------|
| `threads` / `messages` | Companion chat + workflow append |
| `chat_messages` | Legacy plan-item examiner/echo turns via `/v1/days/.../chat` |

Web ChatPage uses threads only. No schema drop in this change.
