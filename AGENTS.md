# Gotit AI — Agent Guide

## Start here

1. Read **[`docs/SYSTEM.md`](docs/SYSTEM.md)** — architecture, stack, shipped features (token-cheap).
2. Then this file for operating rules.
3. Product principles: [`docs/VISION.md`](docs/VISION.md).

gotit-ai is a **personal single-user** system for long-term technical growth.
Daily learning companion: agents talk in threads, remember weaknesses, run
verify workflows. **Verified = done.** Chat owns the surface; verification is
the core loop (mastery criterion = pass the gate). Not multi-tenant SaaS —
see `docs/PRODUCT.md`.

## Stack & commands

See `docs/SYSTEM.md` (including **Runtime processes**: `gotit-api` /
`gotit-mcp` / Web; **no** in-process worker; OpenClaw owns digest cron).
Common:

```bash
uv sync --all-extras
uv run gotit-api          # :8787 by default
uv run gotit-mcp
cd web && npm run dev     # :5173
./scripts/gate.sh
```

## Iron Laws

1. Do not delete user learning data / Postgres volumes without explicit human approval.
2. Do not commit secrets (`.env`, API keys).
3. Runtime config changes require a human edit to `.env` / compose — agents propose, humans apply.
4. Keep verification logic in `src/gotit/core` — no FastAPI/MCP imports inside core.
5. REST and MCP tools share the same domain operations and schemas.
6. Mastery gate is **deterministic code**, never an LLM.

## OpenSpec (non-trivial work)

Specs live in Git under `openspec/`. Chat is not the source of truth.

| When | What |
|------|------|
| Start | Scan active `openspec/changes/*/` — **merge if same subdomain / surface / follow-up**; else new folder (proposal → design → tasks) |
| Build | Check off `tasks.md` |
| Finish | Sync; archive when done — **before commit/PR** |

Do **not** open a sibling change for work that belongs in an open parent (e.g.
OpenClaw writeback → `companion-os`). See `.cursor/rules/openspec.mdc`.

Skip only for trivial typos/comments/tiny docs. Hooks may **ask** on commit/PR
if code changed without OpenSpec / `docs/SYSTEM.md` updates.

## Doc sync

| Doc | Role |
|-----|------|
| `docs/SYSTEM.md` | Agent onboarding snapshot — update when arch/features change |
| `README.md` / `README.zh-CN.md` | Humans — update when pitch / quick start / roadmap drift |
| `docs/VISION.md` | Principles |

Rule: `.cursor/rules/docs-sync.mdc`. Prefer editing SYSTEM over long chat dumps.

## OpenClaw

- MCP tools in `src/gotit/mcp/server.py`; guidance in `skills/gotit/SKILL.md`
- Do not implement Feishu/Telegram/etc. inside gotit — that stays on OpenClaw

## Commits

English Conventional Commits — see `.cursor/rules/git-commits.mdc`.
Split by OpenSpec / user-facing story (not one mega `feat: ship A, B, and C`).
One vertical slice for a single story may still span `core`+`api`+`web`.
