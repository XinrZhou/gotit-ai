# day-close-ritual — design

## Boundaries

| 动 | 不动 |
|----|------|
| 日闭环状态与收工 API | mastery gate、排程间隔公式 |
| companion / 空态 CTA | Chat 气泡块组件体系（可先用现有按钮） |
| 复盘摘要字段 | OpenClaw 内发微信（digest skill 只读新字段即可） |

## A — 条件（代码）

**钉死字段**（alembic，不用 memory）：

- `learning_days.closed_at`（nullable timestamptz）
- `learning_days.close_passed_count` / `close_still_owed_count`（nullable int）
- `learning_days.close_note`（nullable short text）

「建议收工」启发式（非强制）：`due_claims` 空且今日 plan 中带 `claim_id` 的项均为 `verified`（或无此类项）；**强制路径**只有用户点收工 / `close_day`。

收工后：`/v1/today` 带 `day_closed=true` + `close_summary`；空态隐藏「一键开考」强 CTA，保留安静「继续练」入口。

## B — Surfaces

- `POST /v1/days/today/close`（idempotent）+ `GET` 带 close 状态
- MCP `gotit_close_day`；companion `close_day`
- 空聊天 / SessionStart：「今天收工」；确认后短复盘一句话

## C — Digest 钩子

晚间 wrap 若存在 `day_close` 摘要，优先用其数字，避免再猜。digest skill 只读，不在本 change 改推送策略。

## Risks

- 与「仍有欠账却想收工」：允许，摘要如实写还挂几道，不羞辱
- 与 interview ramp nudge：收工不取消已排面试提醒；仅抑制「今日开考」推销
