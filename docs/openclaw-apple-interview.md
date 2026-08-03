# OpenClaw Apple 面试日历桥

面试安排写入 gotit 后，**自动**同步到 Mac **日历**（默认名「面试」；
不存在则用本机第一个日历）。

```text
Settings / MCP ──► interview ops ──► gotit.bridge.calendar
                                              │
                                              ▼
                               skills/apple-interview (JXA)
                                              │
                                              ▼
                                         Calendar.app
```

事件描述含 `[gotit-interview:<uuid>]`，便于更新与删除。
完成 / 取消 / 删除会移除对应日程。提醒偏移沿用 `remind_offsets_hours`
（默认面试前 24h、2h）。

权限：系统设置 → 隐私与安全性 → **日历**。

跳过：`GOTIT_SKIP_APPLE_SYNC=1`

相关：日计划 ↔ 提醒事项见 [`openclaw-apple-plan.md`](openclaw-apple-plan.md)。
