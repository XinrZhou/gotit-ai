# gotit-ai

**Got it? Prove it.**

*Don't mark it learned until you've been checked.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![uv](https://img.shields.io/badge/packaging-uv-DE5FE9)](https://docs.astral.sh/uv/)
[![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TypeScript](https://img.shields.io/badge/Web-React%20%2B%20Vite-3178C6?logo=react&logoColor=white)](https://react.dev/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)

**English** | [中文](README.zh-CN.md)

---

## Why gotit-ai?

Most study tools help you **collect** — notes, highlights, saved threads. Few help you **verify**.

You finish a chapter, an article, a deep dive on Agent Runtime. It feels familiar. You bookmark it. Two days later, a follow-up question lands and the answer collapses into "I think I've seen this…"

That gap has a name: **false fluency** — looking like you got it, without being able to show it.

> *"I don't need another second brain that stores more."*
> *"I need a small team that asks: got it — for real?"*

**gotit-ai** is a multi-agent learning checkbench. Paste what you studied. A team runs checks — probes, short drills, apply-it tasks, teach-backs — in whatever form fits. Fail → targeted coaching → check again. Pass only when evidence says so.

Most tutors summarize. gotit-ai **stress-tests whether you actually got it.**

## What It Does

| Capability | What It Means |
|-----------|---------------|
| **Multi-Agent Check Loop** | Librarian gathers → Examiner checks → Coach patches gaps → Examiner rechecks |
| **Multiple Check Modes** | Probing Q&A, short drills, apply-it tasks, teach-backs — not locked to one format |
| **Mastery Gate** | A topic stays "not yet" until it passes; no silent promotion from "I read it" |
| **Missed-Item Regression** | Failed points land in a retry queue — recheck later, not just scroll past |
| **Context on a Budget** | Checks inject the claim under test, not the whole notebook |
| **OpenClaw via MCP** | Channel inbox stays on OpenClaw; gotit exposes verification tools |
| **Tiny Eval Harness** | Snapshot cases + held-out rechecks so "improvement" is measurable |
| **Trace & Metrics** | Rounds, pass/fail, latency, token use — compare "summary only" vs "check first" |

## Architecture

```
OpenClaw (channels / sessions)
        │  MCP + Skill
        ▼
gotit-ai  (Python / uv)
  core verify-loop · FastAPI · MCP · harness
  Postgres · Redis · React web
```

**Design rule:** summarizing is cheap. **Verification is the product.**

## Stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.12 · **uv** · FastAPI · MCP |
| Data | Postgres 16 · Redis 7 |
| Web | React · Vite · **npm** (under `web/`) |
| Engineering | OpenSpec · ADR · AGENTS.md · `scripts/gate.sh` |
| Integration | OpenClaw MCP (`skills/gotit`) |

## Quick Start

**Prerequisites:** Python 3.12+ · [uv](https://docs.astral.sh/uv/) · Node.js 20+ · Docker · LLM API key

```bash
# 1. Clone
git clone https://github.com/<you>/gotit-ai.git
cd gotit-ai

# 2. Python deps
uv sync --all-extras
cp .env.example .env   # set GOTIT_API_KEY / LLM_API_KEY

# 3. Infra
docker compose up -d postgres redis

# 4. API
uv run gotit-api
# → http://127.0.0.1:8787/health

# 5. Web UI
cd web && npm install && npm run dev
# → http://127.0.0.1:5173

# 6. Quality gate
./scripts/gate.sh
```

### OpenClaw MCP (stdio)

```json
{
  "mcp": {
    "servers": {
      "gotit": {
        "command": "uv",
        "args": ["run", "--directory", "/absolute/path/to/gotit-ai", "gotit-mcp"]
      }
    }
  }
}
```

See `skills/gotit/SKILL.md` for agent guidance.

## How a Round Works

1. **Ingest** — paste notes, a doc chunk, or a study outline  
2. **Check** — Examiner picks a mode and runs one or more checks  
3. **Gate** — pass → mark mastered (for now); fail → Coach on the gap only  
4. **Recheck** — Examiner runs again; still fail → stay in the missed-item queue  
5. **Regress** — later, pull missed items and prove it again  

## Roadmap

Built in the open. Honest status.

| Feature | Status |
|---------|--------|
| Repo scaffolding (uv / API / MCP / web / harness stubs) | Done |
| OpenSpec + VISION + ADRs | Done |
| Librarian / Examiner / Coach loop | In Progress |
| Multiple check modes | Planned |
| Mastery gate + missed-item queue | Planned |
| MCP streamable-http + OpenClaw skill polish | Planned |
| Web UI (paste → check → results) | In Progress |
| Mini harness (snapshot + holdout) | Planned |
| "Summary only" vs "check first" A/B | Planned |

## Philosophy

### Collect vs Check

- **Collect** = more notes, more context, more "I'll review later."  
- **Check** = a claim under test, a mode, a pass/fail, a retry path.

gotit-ai biases hard toward **check**. Storage is support infrastructure, not the hero feature.

### Three Principles

| # | Principle | Meaning |
|---|-----------|---------|
| P1 | Verified = got it | Confidence is not evidence |
| P2 | Fail is useful | A miss should become a small lesson + a recheck, not shame |
| P3 | Form follows the claim | Probe, drill, apply, or teach-back — pick what tests the idea |

## Learn More

- **[README.zh-CN.md](README.zh-CN.md)** — Chinese  
- **[AGENTS.md](AGENTS.md)** — agent / contributor operating guide  
- **[docs/VISION.md](docs/VISION.md)** · **[docs/adr/](docs/adr/)**  

## Contributing

PRs welcome once the core loop is runnable.

- Keep the product about **verification**, not another note dump  
- Prefer small, reviewable changes; English Conventional Commits  
- Use OpenSpec for non-trivial changes; add harness evidence when behavior shifts  

## License

[MIT](LICENSE) — Use it, modify it, ship it. Keep the copyright notice.

---

*Don't mark it learned until you've been checked.*

**Got it? Prove it.**
