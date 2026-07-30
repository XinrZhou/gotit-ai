# verify-surface — design

## Task 1 — Structured verdict UI

### Data (already persisted)

Examine agent messages carry:

```text
metadata.workflow = "examine"
metadata.step = "agent"
metadata.verdict = "passed" | "almost" | "owe_next"   # when claim done
metadata.session_done = bool
metadata.claim_id = uuid?
```

`examine_agent_text` still prefers natural `follow_up`; UI must not rely on
parsing the bubble string.

### UI

- Shared quiet chip: `过了` / `还差点` / `欠着下次` — `--fill` bg, no ink pill.
- Optional muted line `本主题考完` when `session_done`.
- Chat thread: render under examine agent bubbles when `metadata.verdict` set.
- Examine panel: extend `ChatTurn` / `ChatMsg` with optional `verdict` +
  `session_done`; `useExamine` keeps API fields; `ChatLog` shows chip.

### Non-goals (task 1)

- Score / evidence / writeback cards
- Changing persistence shape
- Critic model / failure inject (tasks 2–3)

## Tasks 2–3

- Task 2 (done): Critic recheck uses `resolve_llm_binding` /
  `get_critic_model` — identity `llm_config` → `CRITIC_*` → global `LLM_*`.
  Axiom and other agents unchanged. Gate remains deterministic code.
- Task 3: `failure_digest` memory exists; inject budgeted excerpts into Axiom
  examine prompt / context — not a new product surface.
