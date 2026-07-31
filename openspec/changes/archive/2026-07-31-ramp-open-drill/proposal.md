# ramp-open-drill

## Why

面试升温已会建议「去项目深挖」，但对话里不能像「开考」一样一点就进 drill——仍要顶栏点工作流再填 picker。对上 PRODUCT §1（少点来点去）与 P4 收尾。

## What changes

| 块 | 内容 |
|----|------|
| A | Companion `start_drill`（prepare-only `open_drill`；不跑 Sage） |
| B | Orchestrator lift `metadata.open_drill`；气泡安静「深挖」→ 立刻 POST `/v1/drill/sessions` |
| C | `InterviewUpcoming.project_id`；`get_upcoming_interview` 可带 `open_drill` |

## Out

- Companion 内 hard-start Sage（仍走 Web/MCP `start_drill_session`）  
- 自动改 plan / 全 MCP  
- 无简历时假装开练（CTA 可点，409 用人话错误）  

## Acceptance

搭子备好深挖后气泡出现「深挖」；一点即进入 drill 会话（round/project 来自载荷）；无 resume 时错误可读；门与 Sage 路径不变。
