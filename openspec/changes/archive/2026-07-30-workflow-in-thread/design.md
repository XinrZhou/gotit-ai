# workflow-in-thread — design

## Shape

Reuse `messages` + existing `add_message`. Do **not** extend `chat_messages`
(plan-item legacy) or require a new session↔thread FK for v1.

```text
optional thread_id on examine / teach / drill start|continue
        │
        ▼
append_workflow_exchange(session, thread_id, workflow, agent_name, …)
        │  validates thread.user_id
        ▼
add_message(user?) + add_message(agent)  metadata.workflow = examine|teach|drill
```

## Metadata

```json
{
  "workflow": "examine" | "teach" | "drill",
  "step": "answer" | "agent",
  "note_id"?: "...",
  "claim_id"?: "...",
  "topic"?: "...",
  "drill_session_id"?: "...",
  "verdict"?: "passed|almost|owe_next|…",
  "session_done"?: true
}
```

Agent mapping: examine→`axiom`, teach→`echo`, drill→`sage`.

## Agent text

Persist the same learner-visible string the UI shows (follow_up / next_question /
done summary). Empty agent text → skip agent row (still write user answer if any).

## Web

- `workflowThreadId` in shell; ChatPage `startWorkflow` ensures a thread then sets it
- Hooks pass `thread_id: workflowThreadId` on every workflow POST
- Chat stream: quiet badge from `metadata.workflow` (no loud chrome)

## MCP

Same optional `thread_id` on `gotit_examine` / `gotit_teach` /
`gotit_start_drill_session` / `gotit_continue_drill_session`.

## Risks

- Double history (client `history` + DB) until a later change loads history from
  thread — acceptable; write path is additive and opt-in via `thread_id`.
