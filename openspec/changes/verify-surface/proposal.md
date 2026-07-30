# verify-surface — proposal

## Why

Verify is the spine, but users mostly see plain `follow_up` text. Verdict already
lands in thread `metadata.verdict` (`passed` / `almost` / `owe_next`) and is
discarded in the examine panel. Without a quiet structured surface, “Verified =
done” stays invisible.

## What changes

1. **Structured verify result chips** (this change, task 1) — Chat thread +
   examine panel show quiet Apple chips for verdict (+ optional session-done).
2. **Critic independent model** (task 2 — handoff prompt) — Critic may bind a
   different LLM than Axiom.
3. **Failure lessons inject into Axiom** (task 3 — handoff prompt) — Budgeted
   `failure_digest` memory into examine context.

Out: enterprise doc RAG, Skill publish pipeline, interview P4 countdown.

## Impact

- Web: ChatPage, ChatLog, Examine store types
- Later tasks: `core` LLM binding + examine prompt/context — not in task 1
