---
name: digest
description: >-
  Morning/evening WeChat digests for OpenClaw: configurable RSS tech/finance
  briefs, evening appends gotit_today due claims, writes shell_event to gotit.
  Use for cron digests or when the user asks for 早报/晚报/资讯摘要.
---

# digest — 早晚简报（OpenClaw）

落点在 **OpenClaw**（本 skill + Gateway cron），**不是** gotit 内核。
人设：**Tom**；时区默认 **Asia/Shanghai**（见 `config.json`）。
推送后会写回 gotit `shell_event`（观测真源）；见 `docs/openclaw-digest.md`。

## 何时用

- 定时早报 / 晚报 cron 触发
- 用户说「早报」「晚报」「今天有啥科技新闻」
- 用户回「这篇有用」+ 序号 → `gotit_record_interest`（**不要** ingest→examine）

## 确定性脚本（推荐 cron 用）

```bash
uv run python skills/digest/fetch_digest.py morning
uv run python skills/digest/fetch_digest.py evening
# 调试可不写回：
uv run python skills/digest/fetch_digest.py morning --no-writeback
```

- **morning / evening**：RSS ≈5 条；晚间追加 `gotit_today`；脚本文末含 `event_id=…`
- 写回：默认 db `record_shell_event`；`config.json` 的 `gotit.api_url` 非空则走 `POST /v1/shell/events`

## 「这篇有用」

用户回复「这篇有用 2」或「第 3 条有用」（结合最近简报的 `event_id`）：

1. 调 **`gotit_record_interest`**（或 REST `POST /v1/shell/interest`）：
   - `event_id` = 简报里的 id
   - `item_index` = 序号
   - `title` / `link` / 可选 `topic`（若能从条目推断主题）
2. 短回「已记兴趣信号」。
3. **不要** `gotit_ingest` / `gotit_examine`。

## 安装 cron

见 **[docs/openclaw-digest.md](../../docs/openclaw-digest.md)** 或 `./skills/digest/install-cron.sh`。

## 边界

- 禁止在 `src/gotit/` 写微信适配器；RSS 主逻辑只在本 skill。
