# Proposal: apple-interview-calendar

## Why

Settings「面试安排」添加/删除公司后不同步 Apple 日程，用户以为「备考提醒」会进日历。
日计划已有 Reminders 桥；面试缺对称的 Calendar 写回。

## What changes

- Skill `skills/apple-interview/`：Calendar upsert/rm（标记 `[gotit-interview:<uuid>]`）
- `gotit.bridge.calendar`：best-effort 调 skill（`GOTIT_SKIP_APPLE_SYNC` / pytest 跳过）
- REST + MCP 面试 upsert / patch / status / delete 后自动 sync
- Settings「我」旁路文案：面试 → 日历；日计划 → 提醒事项

## Out

- 从 Calendar 反向 import 面试
- 浏览器内读 Apple / 权限探测 UI
- 改 WeChat interview-remind 投递
