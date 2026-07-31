---
name: interview-remind
description: >-
  Cron: poll gotit due interview reminders (D-1 / T-2h) and optional countdown
  ramp nudges (P4 light/warm), WeChat DM, then mark. Delivery only — schedule
  truth stays in gotit.
---

# interview-remind — 面试提醒与升温投递（OpenClaw）

## 流程

### A — Offset 提醒（P3d）

1. `gotit_list_due_interview_reminders`（可选传 `now` ISO）
2. 每条短讯推微信
3. `gotit_mark_interview_reminded(interview_id)`

默认 offsets（gotit）：`[-24, -2]` 小时相对 `scheduled_at`。

### B — 倒计时升温（P4）

1. `gotit_list_interview_ramp_nudges`（prefs 关则空；≤1 条）
2. 短讯推微信（与 A **合并为同一轮 cron**，不另开高频 job）
3. `gotit_mark_interview_ramp_nudged(interview_id)`

分档在 gotit（确定性）：`light`（3–7 天）/ `warm`（1–3 天）。  
`urgent`（≤24h）**不**走 ramp，只靠 A 的 D-1 / T-2h。

## 文案

Offset：

```text
面试提醒 · {company} · {role_title}
时间：{scheduled_at local}
轮次：{round}
```

Ramp：

```text
面试临近 · {company} · {role_title}
约 {hours_until}h 后 · {tier_hint}
{suggest_action}
```

语气克制，不鸡血、不羞辱。

## Cron

建议每 30～60 分钟（同一 job 先 A 后 B）：

```bash
ln -sfn /path/to/gotit-ai/skills/interview-remind \
  ~/.openclaw/workspace/skills/interview-remind
```

本地试跑：

```bash
uv run python skills/interview-remind/fetch_due.py
uv run python skills/interview-remind/fetch_due.py --apply
uv run python skills/interview-remind/fetch_due.py --ramp
uv run python skills/interview-remind/fetch_due.py --ramp --apply
```

## 边界

- 勿在 gotit 内发微信
- 升温可关：`gotit_put_interview_ramp_prefs` / Settings「倒计时升温」
- 不自动开 drill；只建议用户去「项目深挖」
