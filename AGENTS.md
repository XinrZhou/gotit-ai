# Gotit AI — Agent Guide

## Product

gotit-ai is a **learning verification** checkbench: false fluency → examine → coach → recheck → mastery gate.
**Verified = done.** Summarizing is not the product.

## Stack

- Python 3.12+ managed with **uv**
- FastAPI API (`gotit-api`) + MCP server (`gotit-mcp`) for OpenClaw
- Postgres 16 + Redis 7 (Docker Compose)
- React + Vite web UI under `web/` (npm)
- OpenSpec for change lifecycle; ADRs under `docs/adr/`

## Commands

```bash
uv sync --all-extras
uv run ruff check .
uv run mypy src
uv run pytest
uv run gotit-api          # http://127.0.0.1:8787
uv run gotit-mcp          # stdio MCP
uv run python scripts/run_harness.py --label gate   # dev case set
cd web && npm install && npm run dev
docker compose up -d postgres redis
./scripts/gate.sh
```

## Iron Laws

1. Do not delete user learning data / Postgres volumes without explicit human approval.
2. Do not commit secrets (`.env`, API keys).
3. Runtime config changes require a human edit to `.env` / compose — agents propose, humans apply.
4. Keep verification logic in `src/gotit/core` — no FastAPI/MCP imports inside core.
5. REST and MCP tools share the same domain operations and schemas.

## OpenSpec (required for non-trivial work)

Specs live in Git under `openspec/`. Chat history is not the source of truth.

| Step | Action |
|------|--------|
| Start | Create or continue `openspec/changes/<name>/` (`proposal` → `design` → `tasks`) |
| Build | Implement against `tasks.md`; check items off |
| Finish | Sync artifacts to match code; archive to `openspec/changes/archive/YYYY-MM-DD-<name>/` when done |

- Context/rules: `openspec/config.yaml`
- Skip OpenSpec only for trivial typos/comments/tiny docs
- Cursor hooks: `sessionStart` injects this workflow; `stop` follow-up if code changed without OpenSpec updates (see `.cursor/hooks.json`)
- Optional CLI skills: `openspec init --tools cursor` then `/opsx-propose` / `/opsx-apply` / `/opsx-archive`

## OpenSpec (non-trivial work)

Specs live in Git under `openspec/`. Chat is not the source of truth.

| When | What |
|------|------|
| Start a feature | `openspec/changes/<name>/` with proposal → design → tasks |
| While building | Check off `tasks.md` |
| Ready to keep | Sync artifacts; archive when done — **before commit/PR** |

- Skip OpenSpec only for trivial typos/comments/tiny docs
- Cursor hooks (`.cursor/hooks.json`): `sessionStart` injects rules; `beforeShellExecution` may **ask** on `git commit` / `gh pr create` if code changed without OpenSpec updates
- No automatic OpenSpec sync on every agent stop (avoids documenting throwaway work)
- Optional: `openspec init --tools cursor` then `/opsx-propose` / `/opsx-apply` / `/opsx-archive`

## OpenClaw

- Primary integration: MCP tools `gotit_health`, `gotit_ingest`, `gotit_examine`, …
- Skill guidance: `skills/gotit/SKILL.md`
- Do not implement Feishu/Telegram/etc. inside gotit — that stays on OpenClaw.

## Commits

English Conventional Commits — see `.cursor/rules/git-commits.mdc`.
