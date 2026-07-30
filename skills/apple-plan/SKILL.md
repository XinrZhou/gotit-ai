---
name: apple-plan
description: >-
  Sync study plans between Mac Reminders (primary) and gotit daily plan_items.
  Import: Reminders→gotit. Push: gotit→Reminders (auto after upsert / digest).
  Rm: delete gotit + Reminders. Notes import is secondary. Never reads Apple
  from gotit core.
---

# apple-plan — Mac 提醒事项桥（OpenClaw）

**提醒事项（待办）是手机侧入口**；gotit 仍是日计划 / 验证真源。
写入只设到期日+时间，**不发通知**。全天 sync 用 `--reconcile` 清掉已删计划。

## 何时用

- 「导入计划」→ Reminders → gotit
- 对话新建：`gotit_upsert_plan_item(day, title, due_time=HH:MM)` — **MCP 会自动 push**
- 「删除…」→ `gotit_delete_plan_item`（自动清提醒）或 `rm --apply`
- 早推 digest：先 import 再 push（软双向）

## 命令

```bash
cd /path/to/gotit-ai

uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply

uv run python skills/apple-plan/import_plan.py push --day 2026-07-30 --apply --reconcile

uv run python skills/apple-plan/import_plan.py push \
  --day 2026-07-30 --title "刷动态规划" --time 19:00 --apply

uv run python skills/apple-plan/import_plan.py rm \
  --day 2026-07-30 --title "刷动态规划" --apply
```

## OpenClaw / 微信

1. 理解 `day` + 干净 `title` + `due_time=HH:MM`（不要只把时间塞进标题）
2. `gotit_upsert_plan_item(day, title, due_time="19:00")` → 自动写提醒事项
3. 短回：「已写入 gotit，并同步到提醒事项「学习计划」· 19:00」

删除：`gotit_delete_plan_item(day=…, title=…)`。

## 边界

- 禁止在 `src/gotit/core` 调 Apple；桥在 `gotit.bridge.reminders` + 本 skill
- 本机需 Reminders 权限；可用 `GOTIT_SKIP_APPLE_SYNC=1` 跳过
