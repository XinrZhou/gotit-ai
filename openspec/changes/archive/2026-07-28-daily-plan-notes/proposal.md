# Daily plan + notes (verification-oriented)

> **Archived 2026-07-28** — delivered in commit `3ab9388`. All items shipped.
> The examine stub's `passed` flag was later superseded by the continuous
> verdict (`passed|almost|owe_next`) in the `agent-rewrite` change.

## Why

Learners need a day-scoped place to plan what to verify and store notes agents can consume — without turning gotit into a second brain. Plans and notes support the check loop; mastery still requires evidence.

## Scope

- In: Postgres persistence for learning days, plan items (manual + queue-fill), day notes; REST + MCP parity; thin Web UI; note → ingest → claims; examine stub writeback to plan/claim status; `gotit_today` with truncated context
- Out: multi-user auth, calendar sync, rich text / folder trees, full Librarian/Examiner/Coach LLM wiring

## Non-goals

- Checkbox-as-mastery (plan completion = check evidence)
- Replacing the learner’s judgment on *what* to study long-term (queue suggests *what to verify today*)
