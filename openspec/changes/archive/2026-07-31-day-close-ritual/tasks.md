# day-close-ritual — tasks

## A — Core + ops

- [x] 日收工模型/字段（alembic 或 memory 方案二选一，design 钉死）
- [x] `ops`：`close_today` / 读 close 状态；idempotent
- [x] `/v1/today`（或等价）暴露 `day_closed` + 短摘要
- [x] 单测：欠清建议态、主动收工、重复 close

## B — Surfaces

- [x] REST + MCP `gotit_close_day`
- [x] companion `close_day` + tool trail 摘要
- [x] 空态 / 今日简报「收工」CTA；`day_closed` 时弱化开考强推

## C — Docs / gate

- [x] 相关 pytest；`uv run pytest` 本域测通过
- [x] 追加 `docs/SYSTEM.md` 一句；勾选本 tasks
- [x] 不改 README 大段，除非用户可见入口文案需点名
