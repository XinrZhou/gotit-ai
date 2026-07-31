# SYSTEM — agent onboarding snapshot

> **Read this first** when starting a new agent session. Keep it short.
> Update this file when architecture, stack, or shipped features change —
> then mirror user-facing bits into `README.md` / `README.zh-CN.md`.
> Last reviewed: 2026-07-31.

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
alembic/versions/  0001…0011 (… + interviews + calibration + interview ramp)
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
- **Daily verify brief**: empty chat / empty thread / examine picker show
  owed (`due_claims` from `/v1/today`) + today's plan with one-tap 开考
  (claim-id or note-id examine); each owed row shows quiet `due_reason_text`
  (why today — overdue / almost / scheduled / confuse / queued)
- **Chat plan grounding**: each companion turn gets today's `plan_items` skeleton
  (Asia/Shanghai); ask-plan replies are enforced as short opener + exact markdown
  list (no paraphrased times/items in the opener)
- **Companion builtin tools** (whitelist, not full MCP): chat turns with an LLM key
  inject `get_today` / `list_due_claims` / `start_examine` / `get_failure_lessons` /
  `add_memory` / `get_upcoming_interview` via `api/companion_tools.py` → `db.ops`;
  calls land on agent message `metadata.tool_calls` (name / args_digest / ok /
  summary; `start_examine` ok also attaches `open_examine` + message-level
  `metadata.open_examine`). Chat bubbles show a quiet tool trail; one-tap「开考」
  follows into examine (same `/v1/examine` path). Stub (no `LLM_API_KEY`) skips
  tools and does not fake writes. `start_examine` only prepares open-examine
  (+ soft plan/in_progress); mastery still Critic + gate.
  REST + MCP `gotit_post_message` share `chat_orchestrator` (same tools).
- **Workflows in ChatPage**: 考我 / 回讲 / 项目深挖 (embedded pages; entry in
  conversation top bar)
- Library = left **drawer overlay** (notes / projects only)
- Composer: agents/skills behind `+` tray; type `@` to switch sticky
  companion (strip token, no `@` in body); quiet Apple select; active skill
  shows as a clearable chip on the composer meta row
- Chat reading column centered (~720px); thinking toggle is quiet text (not a
  pill); workflow bar hint + ModeHeader「正在…」context
- **Settings** (conversation top-right account): 资料 / Skills / MCP / 计划推送 / 动态 — profile + DIY skill
  install/view/edit + MCP connectors；**计划推送** = 早/晚计划 cron + 可选 AI/YouTube 源
  （「保存并同步」→ OpenClaw cron）；
  动态 = OpenClaw 推送/兴趣写回（分类/时间筛选；列表主标题为当日 subject）；资料含 Apple 计划桥导入说明
- Nav rail = brand + library + threads (no account footer)
- Conversation top-right: **弱点图谱** (fullscreen mastery graph) + account /
  Settings
- **Verify loop**: examine → critic recheck → deterministic gate → trajectory / SR weighting
  + mastery-graph writeback (`fail_events`, `confused_with` edges)
  + Critic may bind a distinct OpenAI-compatible model via
    `agent_identities.llm_config` (`model` / `base_url` / `api_key_env`) or
    `CRITIC_MODEL` / `CRITIC_BASE_URL` / `CRITIC_API_KEY` (fallback: global `LLM_*`)
  + Shared finalize (`api/verify_finalize.py`) for **thread verify and `/v1/examine`**
    claim-close (note/topic/single) — same Critic + gate + trajectory path
  + **Spaced review** (`core/schedule.py`, deterministic — never LLM):
    `passed` clears due; `almost` stays due today; `owe_next` →
    `next_review_at = as_of + min(30, 1+2×prior_failures)`;
    `due_claims` / fill-from-queue sort by overdue → fail severity → confuse weight;
    `/v1/today` due items carry `due_reason_code` / `due_reason_text`;
    re-examine injects top `confused_with` neighbor short labels (budgeted)
- **Cold-start calibration** (`core/calibration.py` + `db.ops.calibration`):
  CAT-lite (2PL info + adaptive θ + knowledge rotate + early stop ≤10);
  binary self-check (no Critic); correct→`passed`, incorrect→`almost` +
  `fail_event(reason=calibration)` + calibration-only confuse seed;
  REST `/v1/calibration/*` + MCP `gotit_calibration_*` + synthetic replay;
  empty chat CTA「先摸底一下」when owed empty but claims exist
- **Verify surface**: examine agent turns show quiet mastery chips（过了 / 还差点 /
  欠着下次；主题考完另标）；chip 读 `metadata.verdict`，不解析气泡文案
  + **VerifyTrajectory** 考→核→门 step row from `examine_verdict` /
    `recheck_verdict` / `gate_verdict`
- **Workflow turns in thread**: examine / teach / drill optionally append to the
  active companion `messages` stream (`metadata.workflow`); Chat shows quiet badges
- Notes → claims → plan; project + resume-driven drill (resume import =
  projects + `ResumeRecord` only — **no** auto quiz notes); memory; skills; harness
  （个人 gold 对照见 `openspec/changes/archive/2026-07-30-companion-tools-and-schedule/notes-gold.md`：`uv run python scripts/run_gold_compare.py`）
- MCP tools mirror chat/verify/day/skills/connectors/… (see `mcp/server.py`)
- **Mastery graph** (Postgres edges, no RAG): fail → confuse growth; budget subgraph
  injects into Axiom; fullscreen「弱点图谱」from conversation top bar
  (`react-force-graph-2d`); `/v1/obs/graph`

## OpenClaw shell (not in gotit core)

- WeChat channel + MCP mount: `docs/openclaw-wechat.md`；skill `skills/gotit/`
- Plan digests（早=当日计划 / 晚=今日复盘+明日询问；资讯独立默认开·20:00）:
  `docs/openclaw-digest.md`；skill `skills/digest/` + Gateway cron（Asia/Shanghai）
- **Bridge writeback**：digest → `shell_event`；「有用」→ `interest`；
  prefs `/v1/shell/digest-prefs` + `POST /v1/shell/digest-cron/sync`；obs `/v1/shell/*` + `/v1/obs/profile|graph`；Settings「计划推送」「动态」
- **Apple plan bridge**（P1d）：Reminders ↔ `plan_items`（`due_time`；upsert/delete
  自动 sync；早推 import→push reconcile）；`gotit.bridge.reminders` + `skills/apple-plan/`
  （osascript；**不**进 `gotit.core`）
- **Interviews**（P3d + P4）：`InterviewEvent` + REST/MCP due-reminders；
  countdown ramp（deterministic `ramp_tier`：silent/light/warm/urgent；
  light/warm 低频 nudge + `last_ramp_nudge_at` 去重；prefs 可关）；
  Settings「资料」列表 + 升温开关；companion `get_upcoming_interview`；
  投递 `skills/interview-remind/`（offset + ramp 同 cron）
- **Failure digest**（P3b）：examine `almost|owe_next` → `failure_digest` memory（同 claim+verdict
  去重）；`skills/failure-digest/` 推微信；再考时 **budgeted** 注入 Axiom（同 claim /
  confuse 邻居 / 同 topic；`FAILURE_LESSON_MAX_ITEMS=3` · `MAX_CHARS=600`）
- **Voice teach / coding**（P3c/P2）：OpenClaw skills `voice-teach` / `coding`（workspace allowlist）

## Not done yet (honest)

- Broad per-agent multi-model binding beyond Critic (Axiom/others still share
  global `LLM_*`; Critic may use `identity.llm_config` or `CRITIC_*`)
- Broad agent-as-tool beyond the companion **builtin whitelist** + optional user
  MCP connectors (no auto-mount of the full gotit MCP catalog into chat)
- Rich profile / full KG store beyond mastery confuse edges (depends_on later)
- Axiom harness holdout UI
- Auto-start drill from ramp nudge（v0 只建议 + 深链到「项目深挖」）

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
