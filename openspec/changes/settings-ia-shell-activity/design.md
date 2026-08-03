# Design: settings-ia-shell-activity

## IA

```text
设置 Modal
  我 → profile, resume, interviews, Apple sync one-liner
  提醒 → DigestPrefsPanel
  高级 → Skills list + MCP list (existing sheets)

右上角: 弱点图谱 | 动态 | 账号
动态 → Modal fill + ShellActivityPanel (select / delete / batch)
```

## Delete semantics

Only `shell_event` and `interest` kinds. Wrong kind → 400; missing → 404 (single).
Batch skips unknown ids and non-activity kinds; returns `deleted` count.

## Copy

| Old | New |
|-----|-----|
| 倒计时升温 | 临近备考提醒 |
| 升温提示 | (removed from UI copy) |
