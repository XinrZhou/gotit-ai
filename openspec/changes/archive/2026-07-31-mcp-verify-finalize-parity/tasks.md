# Tasks — MCP verify finalize parity

- [x] `gotit_examine` claim-close paths use `finalize_examine_with_gate`
- [x] `gotit_examine` injects budget subgraph + failure lessons (REST parity)
- [x] `gotit_start_verify` uses shared finalize after examine
- [x] Test: MCP direct verdict → Critic + gate meta (stub Critic)
- [x] Sync `docs/SYSTEM.md` (MCP examine / verify share finalize)
- [x] `uv run pytest tests/test_mcp_verify_finalize.py tests/test_daily_verify_loop.py -q`
- [x] `ensure_db` must not replace a live API engine (memory DB safety)
