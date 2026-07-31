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

You finish a chapter. It feels familiar. Two days later a follow-up lands and the answer collapses into "I think I've seen this…"

That gap is **false fluency** — looking like you got it, without being able to show it.

> *"I don't need another second brain that stores more."*
> *"I need a small crew that talks with me daily — and asks: got it, for real?"*

**gotit-ai** is a **daily learning companion**: personality-bearing agents chat with you in threads, remember weak spots across sessions, and run a verify workflow when it's time to prove it. Pass only when evidence says so — the mastery gate is **deterministic code**, never an LLM shrug.

## What It Does

| Capability | What it means |
|-----------|---------------|
| **Companion chat** | Threads, @mention, in-character replies with memory; today's plan brief injected so「今日计划」is grounded; whitelist tools (`get_today` / due / open-examine / open-drill / failure lessons / memory / upcoming interview) with quiet bubble trail + one-tap「开考」/「深挖」 |
| **A2A handoff** | Agents can cede the floor to a peer in the same turn (ball custody) |
| **Workflows** | 考我 / 回讲 / 项目深挖 — started from the chat shell; turns land in the thread |
| **Daily brief** | Empty chat shows owed + today's plan with one-tap 开考 |
| **Cold-start calibration** | Few high-info probes to seed schedule + confuse graph; empty chat CTA when nothing owed yet |
| **Verify loop** | Examine → Critic recheck → **deterministic gate** → trajectory / spaced review (interval grows with prior fails; due rank + confuse neighbors) / mastery-graph (same path for chat verify and `/v1/examine`) |
| **Notes → claims** | Ingest study material into testable claims + daily plan |
| **Resume drill** | Project / resume-driven mock interview (Sage) |
| **Settings** | 资料 / Skills / MCP / 计划推送 / 动态 — profile, DIY skills, plan push prefs, OpenClaw activity |
| **OpenClaw via MCP** | Optional channel; gotit exposes the same domain ops as REST |
| **Harness** | Snapshot cases so prompt/skill changes stay measurable |

Crew (UI nicknames): **章鱼哥** (examiner) · **海绵宝宝** (curator) · **派大星** (teach-back) · **桑迪** (drill) · **凯伦** (critic).

## Architecture

```
React web (ChatPage = main surface)
        │  REST
        ▼
gotit-ai (Python / uv)
  core/     identity · messaging · agents · verify-loop · skills
  db/ops/   shared domain ops (REST + MCP)
  api/      FastAPI routes + A2A chat orchestrator
  mcp/      OpenClaw tools (thin)
  Postgres · Redis
```

**Design rule:** the companion owns chat. **Verification is the spine**, not a headless pipeline. OpenClaw is an optional distribution channel.

## Stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.12 · **uv** · FastAPI · MCP |
| Core | `gotit.core` — framework-free |
| Data | Postgres 16 · Redis 7 (SQLite OK for local/dev) |
| Web | React · Vite · **npm** (`web/`) |
| LLM | OpenAI-compatible endpoint (e.g. Zhipu `glm-4-flash`) |
| Engineering | OpenSpec · ADR · `docs/SYSTEM.md` · `scripts/gate.sh` |

## Quick Start

**Prerequisites:** Python 3.12+ · [uv](https://docs.astral.sh/uv/) · Node.js 20+ · Docker (or SQLite) · LLM API key

```bash
git clone https://github.com/<you>/gotit-ai.git
cd gotit-ai

uv sync --all-extras
cp .env.example .env
# set GOTIT_API_KEY, LLM_BASE_URL, LLM_API_KEY, LLM_MODEL

docker compose up -d postgres redis   # or use SQLite in .env

uv run gotit-api
# → http://127.0.0.1:8787/health

cd web && npm install && npm run dev
# → http://127.0.0.1:5173

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

See `skills/gotit/SKILL.md`. WeChat channel: `docs/openclaw-wechat.md`.
Morning = today's plan; evening = today wrap + tomorrow plan Q&A;
news = separate 20:00 RSS job by default (news separate, optional off):
`docs/openclaw-digest.md`, `skills/digest/`.
Apple Reminders/Notes → gotit plan: `docs/openclaw-apple-plan.md`,
`skills/apple-plan/`.

## How it feels day-to-day

1. **Talk** — open a thread, @ a companion, optionally load a skill  
2. **Ingest** — add notes; extract claims into today's plan  
3. **Verify** — from chat, start 考我 / 回讲 / 深挖  
4. **Gate** — Critic rechecks; code decides pass / almost / owe-next  
5. **Remember** — outcomes land on a trajectory so the next session is sharper  

## Roadmap

| Feature | Status |
|---------|--------|
| Companion chat + identities + memory | Done |
| A2A handoff + ball custody | Done |
| Chat-first nav (workflows embedded) | Done |
| Verify loop + deterministic gate + Critic | Done |
| Notes / claims / plan / resume drill | Done |
| REST ↔ MCP parity + harness gate | Done |
| OpenClaw WeChat digests (morning plan / evening wrap+tomorrow / optional news) | Done (P1c) |
| OpenClaw→gotit shell writeback + Settings「计划推送」「动态」 | Done |
| Apple plan bridge (Reminders/Notes → gotit plan_items) | Done (P1d) |
| Mastery graph (fail events, confused_with, fullscreen from chat top bar) | Done |
| Persist workflow turns into thread history | Done |
| Interview schedule + due reminders | Done (P3d) |
| Interview countdown ramp (tier + optional nudge) | Done (P4) |
| Failure digest / voice-teach / coding skills | Done (P3b/P3c/P2) |
| Companion builtin tools (today/due/examine/memory + tool trail) | Done |
| Chat UI for tool trail + one-tap follow start_examine | Done |
| One-tap drill from open_drill / upcoming interview | Done |
| Real agent tool-calling against full MCP catalog | Next |
| Per-agent multi-model binding | Next |

## Philosophy

| # | Principle | Meaning |
|---|-----------|---------|
| P1 | Verified = got it | Confidence is not evidence |
| P2 | Fail is useful | A miss → lesson + recheck on a trajectory |
| P3 | Form follows the claim | Probe, drill, apply, teach-back |
| P4 | Context on a budget | Inject the claim under test, not the whole notebook |
| P5 | Harness-backed evolution | Prompt/skill changes need evidence |
| P6 | Stable personality + rubric | Persona drift ≠ judgement drift |
| P7 | Gate is code | Never let an LLM be the mastery judge |

## Learn More

- **[README.zh-CN.md](README.zh-CN.md)** — Chinese  
- **[docs/SYSTEM.md](docs/SYSTEM.md)** — concise architecture snapshot (agents: start here)  
- **[AGENTS.md](AGENTS.md)** — contributor / agent operating guide  
- **[docs/VISION.md](docs/VISION.md)** · **[docs/adr/](docs/adr/)**  

## Contributing

- Keep the product about **companion + verification**, not another note dump  
- Small reviewable PRs; English Conventional Commits  
- Non-trivial work → OpenSpec; sync `docs/SYSTEM.md` (+ README if user-facing) before commit/PR  

## License

[MIT](LICENSE)

---

*Don't mark it learned until you've been checked.*

**Got it? Prove it.**
