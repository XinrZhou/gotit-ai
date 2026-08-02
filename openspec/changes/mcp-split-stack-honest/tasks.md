# Tasks: mcp-split-stack-honest

- [x] Split `mcp/server.py` → `app.py` + `common.py` + `tools/*`
- [x] Keep `gotit-mcp` entry + `from gotit.mcp.server import gotit_*` re-exports
- [x] Update `docs/SYSTEM.md` (stack honesty, layout, verify spine, personal use)
- [x] Update `README.md` + `README.zh-CN.md` (Redis optional / unused)
- [x] Comment Redis unused in `.env.example`; Compose redis behind `profiles: [redis]`
- [x] `uv run pytest tests/test_mcp_verify_finalize.py tests/test_loop.py -q`
- [x] `uv run ruff check src/gotit/mcp`
