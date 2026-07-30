---
name: failure-digest
description: >-
  After examine almost|owe_next, deliver a short WeChat recap (gap + recheck tip).
  Polls gotit pending failure_digest memories; marks notified after send.
  Same claim+verdict is queued at most once.
---

# failure-digest — 挂题短讯（OpenClaw）

gotit 在 `apply_examine_verdict(almost|owe_next)` 时写入
`memory.kind=failure_digest`（同 claim+verdict 去重）。本 skill **只负责投递**。

## 流程

1. `gotit_list_pending_failure_digests`
2. 对每条发微信短讯（缺口 + 再检提示）
3. `gotit_mark_failure_digest_notified(memory_id)`

## 文案模板

```text
挂题复盘 · {verdict}
「{claim_text}」
再检：打开 gotit 考我，或回「再考这条」。
```

`almost` → 「差一点」；`owe_next` → 「下次再来」。

## Cron（建议每小时）

```bash
# OpenClaw agent turn / cron message:
# 拉取 pending failure digests 并私聊推送，成功后 mark notified。
```

注册示例（与 digest 同 sessions 解析）：

```bash
ln -sfn /path/to/gotit-ai/skills/failure-digest \
  ~/.openclaw/workspace/skills/failure-digest
```

也可本地试跑：

```bash
uv run python skills/failure-digest/fetch_pending.py
```

## 边界

- 不在 gotit 内发微信
- 勿对已 `notified` 的条目重复推
