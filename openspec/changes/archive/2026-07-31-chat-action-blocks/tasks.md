# chat-action-blocks — tasks

## A — Contract

- [x] TS +（如需）Python 侧 metadata 类型/`action_blocks` 约定文档化于 design
- [x] 服务端：tool `list_due_claims` / examine finalize 最小填充路径

## B — Web

- [x] `ActionBlocks` 组件：owed / verdict / 开考·深挖
- [x] 接入 Chat 气泡渲染；点击走现有 API
- [x] Apple 安静样式；块数量上限

## C — Docs / gate

- [x] 前端 build / 相关测或手工清单写在 tasks 注释
- [x] `docs/SYSTEM.md` 一句；不写外部产品对照

<!-- verify: uv run pytest tests/test_action_blocks.py tests/test_companion_tools.py tests/test_open_drill.py tests/test_daily_verify_loop.py tests/test_mcp_verify_finalize.py -q；cd web && npm run build -->
