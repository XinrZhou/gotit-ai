# Proposal: ability-state-projection

## Why

简历与面试叙事需要 **Ability State Model**、**State-driven Workflow**、
**Stateful AI Companion**，但权威仍是 Claim mastery。投影与决策已分散在
Brief / companion / Web CTA；聊天若只靠对话史，体验会退化成普通 Chat。

## What changes

### P0-1 Ability State Projection
只读 per-topic Ability View；REST/MCP/companion 共享 builder。

### P0-2 State-driven Workflow Routing
纯函数 `next_action(state)`；复用 `route_for_claim`；无 Workflow Engine。

### P0-3 Chat Companion State Context
`format_companion_state_brief` + orchestrator 注入：能力摘要 / 已掌握 /
薄弱 / 待验证 / 成长目标 + next_action；只读；硬规则禁止聊天写掌握；
控制体积（topic 上限 + 摘录截断；历史仍用既有 limit）。

## Out

- Ability 表；改 gate / mastery 写口
- Workflow Engine；聊天直接写 mastery
- 全量 claim/trajectory 灌进 prompt

## Success

- 聊天 prompt 含「学习者成长状态」与只读硬规则
- 投影 / next_action / brief 可单测；无 schema migration

## Impact

- `core/ability_projection.py`、`core/next_action.py`、
  `core/companion_state_context.py`、`db/ops/*`、`chat_orchestrator`、
  `agents/runtime.build_chat_prompt`、tests、`docs/SYSTEM.md`
