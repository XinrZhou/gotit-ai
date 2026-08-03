# Design: apple-interview-calendar

## Flow

```text
Settings / MCP
  → db.ops interview write
  → gotit.bridge.calendar.upsert|rm
  → skills/apple-interview/sync_interview.py
  → osascript Calendar.jxa
```

## Event identity

Description contains stable marker `[gotit-interview:<uuid>]`.
Title: `{company} · {role_title}` (+ round if set).
Start = `scheduled_at`; end = start + 1h.
Alarms from `remind_offsets_hours` (hours before start).

`done` / `cancelled` / delete → remove Calendar event.

## Config

`skills/apple-interview/config.json`:
- `calendar_name` default `面试`（找不到则用本机第一个日历）
- `timezone` hint Asia/Shanghai（ISO start already tz-aware）

## Iron

- Not in `gotit.core`
- Best-effort: sync failure must not fail the REST write
