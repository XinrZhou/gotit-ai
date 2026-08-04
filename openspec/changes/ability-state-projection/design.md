# Design: ability-state-projection

## Boundary

| Plane | Role |
|-------|------|
| **SoT** | Claim mastery via `write_mastery_outcome` |
| **Projection** | Ability / Learner / MasterySnapshot — read models |
| **Next action** | Pure decision over projections — not authority |
| **Chat context** | Budgeted brief injected into prompt — **read-only** |

## P0-3 injection

```text
build_companion_state_brief
  → ability + next_action + light prefs
  → format_companion_state_brief (caps: 3 mastered / 3 weak / 3 pending)
chat_orchestrator → run_chat(learner_state_brief=…)
build_chat_prompt → ## 学习者成长状态 + 【成长状态 · 硬规则】
```

Chat history remains capped (`list_messages(limit=20)`); state brief does not
dump full trajectory.

## Explicit non-goals

No mastery write from chat. No workflow engine. No full-history injection.
