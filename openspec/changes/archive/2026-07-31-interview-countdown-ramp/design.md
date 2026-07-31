# interview-countdown-ramp — design

## Boundaries

| 动 | 不动 |
|----|------|
| `core/interview_ramp.py` 分档；ops 列表/mark/prefs | 掌握门、排程公式、P3d offset 提醒语义 |
| OpenClaw skill 投递文案 | gotit 内发微信 |

## A — 分档（代码，非 LLM）

`hours_until = (scheduled_at - now).total_seconds() / 3600`

| tier | 条件 | 触达 |
|------|------|------|
| `past` | `< 0` | 不 nudge |
| `urgent` | `≤ 24h` | **仅**既有 D-1/T-2h；不另加 ramp push |
| `warm` | `≤ 72h`（1–3 天） | 可 nudge：建议项目深挖 |
| `light` | `≤ 168h`（3–7 天） | 可 nudge：轻轻提一句 |
| `silent` | `> 7d` | 不 nudge |

`suggest_action`：轮次人话 + 可选首个 active project 名（无则「简历深挖」）。

## B — 去重与 prefs

- 列：`interview_events.last_ramp_nudge_at`
- 同面试 cooldown：**36h**
- 用户周上限：`max_nudges_per_week`（默认 2）；一次 poll **最多 1** 条（最近一场）
- prefs（memory `kind=interview_ramp_prefs`）：`enabled`（默认 true）、`max_nudges_per_week`
- `enabled=false` → due-nudges 空；upcoming **仍可读**（Settings / companion）

## C — 表面

- `GET /v1/interviews/upcoming` · `GET /v1/interviews/ramp-nudges` · `POST …/ramp-nudged`
- `GET/PUT /v1/interviews/ramp-prefs`
- MCP 镜像；companion `get_upcoming_interview`
- Settings「面试安排」：升温开关 + 行内安静分档文案
- `skills/interview-remind`：poll ramp-nudges → 推送 → mark（与 due-reminders 同 cron）

## Risks

- 与 D-1 同日撞车：urgent 不发 ramp；warm/light 文案克制、≤1/日有效  
- 无 project 时仍给轮次建议，不空喊  
