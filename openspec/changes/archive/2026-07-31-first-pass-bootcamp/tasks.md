# first-pass-bootcamp — tasks

## A — State

- [x] bootcamp 状态（memory 或 prefs）：done / skipped / in_progress
- [x] 空库检测 ops + REST 只读字段（可挂 `/v1/today`）

## B — UI flow

- [x] SessionStart 步进：笔记 → claim → 开考/摸底 → 结果
- [x] 跳过；有数据用户不展示
- [x] 消费 ActionBlocks（若可用）或临时 CTA + TODO 替换

## C — Docs / gate

- [x] 测：空库展示 / 跳过 / 完成后不再弹
- [x] `docs/SYSTEM.md` 一句

<!-- verify: uv run pytest tests/test_bootcamp.py -q -->
