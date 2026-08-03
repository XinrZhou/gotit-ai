---
name: apple-interview
description: >-
  Sync gotit interview events to Mac Calendar. Upsert on create/update;
  remove on delete/done/cancelled. Marker [gotit-interview:<uuid>].
  Never reads Apple from gotit.core — bridge is gotit.bridge.calendar.
---

# apple-interview — Mac 日历桥

面试安排写入 gotit 后，**自动**同步到 Calendar（默认日历名「面试」，
找不到则用本机第一个日历）。事件描述含 `[gotit-interview:<uuid>]` 以便更新/删除。

## 命令

```bash
cd /path/to/gotit-ai

uv run python skills/apple-interview/sync_interview.py upsert \
  --id <uuid> \
  --title "Acme · 后端" \
  --start 2026-08-10T14:00:00+08:00 \
  --alarms 24,2

uv run python skills/apple-interview/sync_interview.py rm --id <uuid>
```

## 权限

系统设置 → 隐私与安全性 → **日历** → 允许终端 / OpenClaw。

跳过：`GOTIT_SKIP_APPLE_SYNC=1`

## 边界

- 禁止在 `gotit.core` 调 Apple
- 不做 Calendar → gotit 反向导入
- WeChat `interview-remind` 仍是另一条触达线
