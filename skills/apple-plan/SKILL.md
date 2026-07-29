---
name: apple-plan
description: >-
  Sync study plans between Mac Reminders (primary) and gotit daily plan_items.
  Import: Reminders→gotit. Push: gotit→Reminders after chat creates a plan.
  Rm: delete gotit + Reminders. Notes import is secondary. Never reads Apple
  from gotit core.
---

# apple-plan — Mac 提醒事项桥（OpenClaw）

**提醒事项（待办）是手机侧入口**；gotit 仍是日计划 / 验证真源。
备忘录仅作次要大段导入。不做完整双向实时同步。

## 何时用

- 「导入计划」「导入提醒」→ Reminders → gotit
- 用户对话「新建明日计划：…」→ `gotit_upsert_plan_item` 后 **必须** `push --apply`
- 「删除…计划」「取消明天的…」→ `gotit_delete_plan_item` + **`rm --apply`**（或只跑 `rm`）
- 手动维护列表「学习计划」后灌进 gotit

## 命令

```bash
cd /path/to/gotit-ai

# 提醒事项 → gotit（默认 dry-run）
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划"
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply

# gotit → 提醒事项（对话建计划后写回 iPhone）
uv run python skills/apple-plan/import_plan.py push --day 2026-07-30
uv run python skills/apple-plan/import_plan.py push --day 2026-07-30 --apply

# 删除（gotit + 提醒事项）
uv run python skills/apple-plan/import_plan.py rm \
  --day 2026-07-30 --title "刷动态规划" --apply

# 备忘录（次要）
uv run python skills/apple-plan/import_plan.py notes --title "学习计划" --apply
```

列表默认「学习计划」；不存在时 `push --apply` 会创建。条目需 **带到期日** 才能被 reminders 导入。

## OpenClaw / 微信（iPhone）

### 对话新建（时间交给 Agent 理解）

用户说法不固定（「明儿晚上七点刷 DP」「后天上午学 Redis」）。**不要**把时间塞进标题靠正则猜。

1. Agent 自己理解 → `day=YYYY-MM-DD`、`time=HH:MM`、干净 `title`（可含主题，不必含「晚上7点」）
2. `gotit_upsert_plan_item(day, title=…)`
3. 立刻写回提醒事项（带通知）：

```bash
uv run python skills/apple-plan/import_plan.py push \
  --day 2026-07-30 --title "刷动态规划" --time 19:00 --apply
```

短回：「已写入 gotit，并同步到提醒事项「学习计划」· 19:00」。

`--time` 由 Agent 填；省略时脚本才回退解析标题里的「晚上7点」等（不可靠）。

### 对话删除

用户：「删掉明天刷动态规划」「取消 7/30 那条 DP」。

1. 理解 `day` + `title`（或先 `gotit_get_plan` 再对齐标题）
2. **优先一条命令**（同时删 gotit + 提醒事项）：

```bash
uv run python skills/apple-plan/import_plan.py rm \
  --day 2026-07-30 --title "刷动态规划" --apply
```

也可：`gotit_delete_plan_item(day=…, title=…)` 再 `rm --title … --apply`（`rm` 会再删 gotit 时若已空则只清提醒）。

短回：「已从 gotit 和提醒事项删掉「…」」。

### 从提醒事项导入

回「导入计划」：

```bash
uv run python skills/apple-plan/import_plan.py reminders --list "学习计划" --apply
```

## 权限

| 能力 | 系统设置 |
|------|----------|
| Reminders | 隐私与安全性 → **提醒事项** |

**不要求** Full Disk Access。详见 `docs/openclaw-apple-plan.md`。

## 边界

- 禁止在 `src/gotit/` 调 AppleScript / EventKit
- 不自动 ingest → examine
- Notes 仍可用，但产品默认话术走提醒事项
