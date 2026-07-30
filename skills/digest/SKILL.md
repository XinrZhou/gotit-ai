---
name: digest
description: >-
  Morning/evening WeChat digests for OpenClaw: morning = today's plan,
  evening = today wrap + tomorrow plan Q&A (never mixes news or 今日待检).
  Optional separate news job for AI/YouTube RSS. Writes shell_event to gotit.
  Use for cron or when the user asks for 早报/晚报/资讯摘要.
---

# digest — 计划触达 + 可选资讯（OpenClaw）

落点在 **OpenClaw**（本 skill + Gateway cron），**不是** gotit 内核。
人设：**Tom**；时区默认 **Asia/Shanghai**。
推送后写回 gotit `shell_event`；见 `docs/openclaw-digest.md`。

## 语义（P1c + evening wrap）

| mode | 内容 |
|------|------|
| `morning` | **今日计划**（先 import 提醒→gotit，再 push reconcile；空计划不写动态） |
| `evening` | **今日复盘**（✓/○）+ **明日计划**询问（有→调整并 push；无→新建）。**禁止**附今日待检 / 资讯 |
| `news` | 仅 AI/YouTube RSS（独立 cron，默认 **开** · 20:00；与早/晚计划分离） |

## 确定性脚本

```bash
uv run python skills/digest/fetch_digest.py morning
uv run python skills/digest/fetch_digest.py evening
uv run python skills/digest/fetch_digest.py news
uv run python skills/digest/fetch_digest.py morning --no-writeback
```

Prefs：优先 gotit `GET/PUT /v1/shell/digest-prefs`（Settings「计划推送」）；文件 `config.json` 为回退。
改 cron 后用 Settings「保存并同步」或 `gotit_sync_digest_cron` / `./skills/digest/install-cron.sh`。

## iPhone 用户：提醒事项 → 导入

推送**不塞深链**。空计划时两条路：

1. 打开手机「提醒事项」列表「学习计划」（带到期日）→ 回「导入计划」
2. 直接对话：「新建明日计划：……」→ `gotit_upsert_plan_item(day, title, due_time=HH:MM)`（自动 push 提醒事项）

- 用户回 **「导入计划」** / 「导入提醒」/ 「同步计划」
  → **转交 `apple-plan`**：`reminders --list 学习计划`（先 dry-run 再 `--apply`）
- 用户对话新建/调整计划后
  → `gotit_upsert_plan_item`（带 `due_time`；自动同步提醒事项）
- 用户 **删除 / 取消** 某条计划
  → `gotit_delete_plan_item`（自动清提醒）
- iPhone 与 Mac 靠 **iCloud 提醒事项**同步

计划相关回复（「调整…」「新建明日计划：…」「删除…」）→ `gotit_upsert_plan_item` / `gotit_delete_plan_item`（自动同步提醒事项）。

## 「这篇有用」

仅针对 **news** 推送。用户回「这篇有用 2」：

1. `gotit_record_interest`（event_id + item_index + title/link）
2. 短回「已记兴趣信号」
3. **不要** `gotit_ingest` / `gotit_examine`

## 安装 cron

`./skills/digest/install-cron.sh`（会读 prefs；`news_enabled` 才注册资讯 job）。

## 边界

- 禁止在 `src/gotit/` 写微信适配器
- 晚报正文不得混入 RSS 或「今日待检」（今日复盘只读 plan_items）
- Apple 备忘录/提醒事项导入 → `skills/apple-plan/`（P1d）
