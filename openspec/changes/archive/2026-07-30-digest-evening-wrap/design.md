# Design — digest evening wrap

## Current (bug for users)

| Job | Body |
|-----|------|
| morning | 今日计划 |
| evening | **仅**明日计划 Q&A（空 → CTA） |

Title「晚报」暗示当日收工，但无今日段落 → 空壳感。

## Target

```
🐱 Tom 晚报
YYYY-MM-DD · HH:MM   ← 今日（推送日）

今日复盘
✓ …（verified / done / …）
○ …（planned / in_progress / deferred）
（无条目 →「今日无计划。」；全完成 → 只列 ✓）

　
明日计划
…（有 → 列表 + 调整/保持；无 → 新建 CTA）
```

## Rules

1. Load **today** + **tomorrow** plans (`load_plan`).
2. Still **no** `今日待检` / RSS in evening body.
3. Writeback skip only when **both** days have no plan substance and no errors
   (today items empty AND tomorrow open picks empty).
4. `shell_event.day` for evening = **today** (wrap day); `subject` prefer
   first open tomorrow title, else first today title.
5. Reminders push still only when tomorrow has open picks.

## Touch

- `skills/digest/fetch_digest.py` + tests
- `skills/digest/SKILL.md` · `docs/openclaw-digest.md` · `docs/SYSTEM.md`
- README digests one-liner if present
