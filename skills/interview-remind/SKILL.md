---
name: interview-remind
description: >-
  Cron: poll gotit due interview reminders (D-1 / T-2h by default), WeChat DM,
  then mark_interview_reminded. Delivery only — schedule truth stays in gotit.
---

# interview-remind — 面试提醒投递（OpenClaw）

## 流程

1. `gotit_list_due_interview_reminders`（可选传 `now` ISO）
2. 每条短讯推微信
3. `gotit_mark_interview_reminded(interview_id)`（写入 `last_reminded_at`，同 offset 去重）

默认 offsets（gotit）：`[-24, -2]` 小时相对 `scheduled_at`。

## 文案

```text
面试提醒 · {company} · {role_title}
时间：{scheduled_at local}
轮次：{round}
备注：{notes}
```

## Cron

建议每 30～60 分钟：

```bash
ln -sfn /path/to/gotit-ai/skills/interview-remind \
  ~/.openclaw/workspace/skills/interview-remind

# OpenClaw cron message example:
# 拉取 gotit due interview reminders，私聊推送后 mark reminded。
```

本地试跑：

```bash
uv run python skills/interview-remind/fetch_due.py
uv run python skills/interview-remind/fetch_due.py --apply
```

## 边界

- 倒计时升温（P4）另案；本 skill 只做到期提醒
- 勿在 gotit 内发微信
