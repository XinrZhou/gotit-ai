# SYSTEM — agent onboarding snapshot

> **Read this first** when starting a new agent session. Keep it short.
> Update this file when architecture, stack, or shipped features change —
> then mirror user-facing bits into `README.md` / `README.zh-CN.md`.
> Last reviewed: 2026-07-29.

## Product (one line)

Daily **learning companion**: personality agents chat in threads, remember
weaknesses, and run verify workflows. **Verified = done.** Chat owns the
surface; verification is the spine.

## Stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.12 · **uv** · FastAPI · MCP (`gotit-api` / `gotit-mcp`) |
| Core | `gotit.core` — **framework-free** (no FastAPI/MCP imports) |
| Data | Postgres 16 + Redis 7 (Compose); SQLite OK for local/dev |
| Web | React + Vite + **npm** under `web/` |
| LLM | OpenAI-compatible (`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`); e.g. 智谱 `glm-4-flash` |
| Specs | OpenSpec · `docs/VISION.md` · `docs/adr/` · this file |
| Gate | `./scripts/gate.sh` (ruff / mypy / pytest / harness / web build) |

Default API port in `.env.example`: **8787** (local overrides may use 8790).

## Layout (where to edit)

```
src/gotit/
  core/          agents, loop, models, identity, messaging, skills
  db/ops/        domain ops (day, note, claim, thread, identity, …) — barrel `__init__`
  api/routes/    one router per subdomain + chat_orchestrator (A2A)
  mcp/server.py  thin MCP → same db.ops
web/src/
  pages/ChatPage   main shell (workflows embed Examine/Teach/Drill)
  store/           shell + domain hooks (useExamine / useTeach / useDrill / …)
  components/      Avatars, ModeHeader, SessionStartPanel, …
alembic/versions/  0001…0007 (… + mastery: fail_events / graph_edges)
openspec/changes/  active + archive/
```

Iron laws: REST ↔ MCP parity via `db.ops`; mastery **gate is deterministic code**, never LLM.

## Agents (UI nicknames)

| id | UI | Role |
|----|-----|------|
| axiom | 章鱼哥 | Examiner |
| compass | 海绵宝宝 | Curator / claims |
| echo | 派大星 | Teach-back |
| sage | 桑迪 | Project drill / interview |
| critic | 凯伦 | Independent recheck |

## Shipped capabilities

- **Chat threads** + @mention routing + **A2A handoff** (`ChatTurn.handoff_to`, ball custody `stage=chat`)
- **Workflows in ChatPage**: 考我 / 回讲 / 项目深挖 (embedded pages; entry in
  conversation top bar; nav rail = brand + threads)
- Library = left **drawer overlay**; 「图谱」opens **fullscreen** mastery graph
- Composer: agents/skills behind `+` tray; quiet Apple select
- **Settings** (nav gear): 资料 / Skills / MCP / 计划推送 / 动态 — profile + DIY skill
  install/view/edit + MCP connectors；**计划推送** = 早/晚计划 cron + 可选 AI/YouTube 源
  （「保存并同步」→ OpenClaw cron）；
  动态 = OpenClaw 推送/兴趣写回（分类/时间筛选；列表主标题为当日 subject）；资料含 Apple 计划桥导入说明
- **Verify loop**: examine → critic recheck → deterministic gate → trajectory / SR weighting
  + mastery-graph writeback (`fail_events`, `confused_with` edges)
- Notes → claims → plan; project + resume-driven drill (resume import =
  projects + `ResumeRecord` only — **no** auto quiz notes); memory; skills; harness
- MCP tools mirror chat/verify/day/skills/connectors/… (see `mcp/server.py`)
- **Mastery graph** (Postgres edges, no RAG): fail → confuse growth; budget subgraph
  injects into Axiom; fullscreen「图谱」(`react-force-graph-2d`); `/v1/obs/graph`

## OpenClaw shell (not in gotit core)

- WeChat channel + MCP mount: `docs/openclaw-wechat.md`；skill `skills/gotit/`
- Plan digests（早=当日计划 / 晚=明日询问；资讯独立可选）: `docs/openclaw-digest.md`；
  skill `skills/digest/` + Gateway cron（Asia/Shanghai）
- **Bridge writeback**：digest → `shell_event`；「有用」→ `interest`；
  prefs `/v1/shell/digest-prefs` + `POST /v1/shell/digest-cron/sync`；obs `/v1/shell/*` + `/v1/obs/profile|graph`；Settings「计划推送」「动态」
- **Apple plan bridge**（P1d）：Reminders ↔ `plan_items`（import / push / rm）；
  MCP `gotit_delete_plan_item`；`docs/openclaw-apple-plan.md` + `skills/apple-plan/`
  （osascript；**不**进 `src/gotit`）

## Not done yet (honest)

- Per-agent multi-model binding in production
- Workflow turns fully persisted into the same thread message stream
- companion-os P2 coding / P3 interview reminders (see `openspec/changes/companion-os/`)
- Broad agent-as-tool coverage beyond user MCP connectors
- Rich profile / full KG store beyond mastery confuse edges (depends_on later)

## Commands

```bash
uv sync --all-extras
cp .env.example .env          # set GOTIT_API_KEY + LLM_*
docker compose up -d postgres redis
uv run gotit-api              # :8787
cd web && npm install && npm run dev   # :5173
./scripts/gate.sh
```

## Doc sync rule

| Doc | Audience | Update when |
|-----|----------|-------------|
| `docs/SYSTEM.md` | Agents (token-cheap) | Arch / stack / features change |
| `README.md` + `README.zh-CN.md` | Humans | Product pitch / quick start / roadmap drift |
| `docs/VISION.md` | Product principles | Principles / non-goals change |
| `openspec/changes/` | Change lifecycle | Non-trivial work |

Before `git commit` / PR: if code changed product behavior, sync **SYSTEM** (and README if user-facing). Hook may ask.
