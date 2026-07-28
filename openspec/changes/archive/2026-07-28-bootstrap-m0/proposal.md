# Bootstrap M0 scaffolding

> **Archived 2026-07-28** — delivered in commit `ea682c8` (repo scaffold) +
> `3ab9388` (daily plan/notes). All in-scope items shipped. The two deferred
> items (real Librarian extraction, streamable-http MCP) were intentionally
> out of scope and picked up by the `agent-rewrite` change.

## Why

Stand up the engineering floor: uv Python package, FastAPI + MCP stubs, React web, Postgres/Redis compose, OpenSpec/ADR layout, OpenClaw skill — so later features do not require stack rewrites.

## Scope

- In: repo layout, health/ingest stubs, verify-loop skeleton, docs, skill
- Out: real Librarian/Examiner/Coach LLM wiring, mastery persistence, streamable-http MCP

## Non-goals

- Channel adapters (Feishu, etc.)
- Production auth beyond API key bearer
