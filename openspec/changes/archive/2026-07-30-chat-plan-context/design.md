# chat-plan-context — design

## Shape

```text
post_message_chain
  └─ get_plan(today Asia/Shanghai) → format_today_plan_brief
       └─ run_chat(..., today_plan_brief=…)
            └─ build_chat_prompt 增加「## 今日计划」段 + 禁止编造指令
```

Formatting lives in `gotit.core.agents.runtime` (framework-free).
Orchestrator loads plan once per user message (shared across A2A turns).

## Brief format

- Cap ~8 items; prefer open statuses first
- Line: optional `HH:MM` + title + short status zh
- Empty → explicit empty sentence (no invented bullets)

## Risks

- Token cost: negligible for typical day plans
- Server TZ vs learner TZ: use `Asia/Shanghai` to match digest prefs default
