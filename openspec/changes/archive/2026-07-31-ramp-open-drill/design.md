# ramp-open-drill — design

## Boundaries

| 动 | 不动 |
|----|------|
| prepare `open_drill` + Chat CTA + store 带参开练 | Critic/gate；MCP hard-start 语义 |
| upcoming 带 `project_id` | 改 P4 分档公式 |

## A — `start_drill`（prepare-only）

参数：`round?` · `project_id?` · `interview_id?` · `direction?`

解析顺序：
1. 无 resume → `ok: false`（仍可记 trail）
2. `round` ← 显式 → interview.round → `tech_1`（normalize 到 DrillRound）
3. `project_id` ← 显式 → 首个 active project

载荷：

```text
open_drill = {
  action, round, direction?, project_id?, project_name?,
  interview_id?, company?, thread_id?, has_resume: bool
}
```

不 `create_drill_session`、不跑 Sage。

## B — UI

- Trail：`start_drill` chip；成功则「深挖」
- `followOpenDrill` → `startWorkflow("drill")` → `onDrillStartWithPayload`（inline POST，避免 setState 竞态）
- 同时有 `open_examine` 与 `open_drill` 时两个 CTA 都可出

## C — upcoming

`InterviewUpcoming.project_id`；`get_upcoming_interview` 对 nearest 附带同构 `open_drill`（便于「快面试了」一轮出 CTA）。
