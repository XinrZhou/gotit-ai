# SYSTEM — agent onboarding snapshot

> **Read this first** when starting a new agent session. Keep it short.
> Update this file when architecture, stack, or shipped features change —
> then mirror user-facing bits into `README.md` / `README.zh-CN.md`.
> Last reviewed: 2026-08-03 (positioning: personal single-user growth loop).

## Product (one line)

**Personal single-user** system for long-term **technical growth**. Daily
learning companion: agents chat in threads, remember weaknesses, run verify
workflows. **Verified = done.** Chat owns the surface; verification is the
**core loop** (mastery criterion = pass the gate). Not a note dump, not
multi-tenant SaaS — warm companion, honest gate.

## Current main path (truth)

```text
打开 App
  → 空聊天 / 今日简报（**欠练** = due ∪ 今日未核销计划；有则一键开练）
  → 无欠时：账清（库里还有料）或「添加资料」→ 出题 →「去开考」
  → 考我 / 回讲（Critic + deterministic_gate）
     · 深挖 = 项目练习场（会话可写 thread；**不过门**，不算掌握）
  → 芯片：过了 / 还差点 / 欠着下次
  → **Done 条**：影响（排程/状态，来自 writeback）+「回今天」（almost 可「接着练」）
  → 回空首页看最新 Brief / 账清；欠清或主动「今日收工」
```

Learner empty states: owed → brief is primary; idle →「添加资料」is primary
(workflows / calibrate / new chat are secondary). Product-story checklist:
`openspec/changes/main-path-converge/design.md` (S1–S5).

旁路（入口不强化）：弱点图谱、顶栏动态、Settings（我/提醒/高级）、
Apple 桥（日计划↔提醒事项；面试↔日历）、Harness API/CLI、CAT 题参写回。当前波次：
- UX / 主路径摩擦：`openspec/changes/main-path-converge/`（作者自管）
- 状态边界收紧：`openspec/changes/state-boundary-tighten/`
- 弱点图谱加深：`openspec/changes/mastery-graph-deepen/`
- 设置 IA + 动态删除：`openspec/changes/settings-ia-shell-activity/`
- 面试 → Apple 日历：`openspec/changes/apple-interview-calendar/`
- 评测闭环 + 失败写回可回归已归档：
  `archive/2026-08-03-eval-harness-loop/`、
  `archive/2026-08-03-failure-writeback-regress/`
不默认拉长 Agent 自主度 / RAG / 自动 adopt。

## Deploy posture

**Personal / single-user** (not multi-tenant SaaS): one `GOTIT_USER_ID` +
shared bearer `GOTIT_API_KEY`. No per-user auth product work planned.
Positioning: `docs/PRODUCT.md`.

## Runtime processes (truth)

| Process | Entry | Role |
|---------|-------|------|
| **API** | `uv run gotit-api` → `gotit.api.main` | Learner Web + REST; Bearer auth |
| **MCP** | `uv run gotit-mcp` → `gotit.mcp.server` | OpenClaw / host tools → same `db.ops` |
| **Web** | `cd web && npm run dev` | SPA; talks **only** to API (not MCP) |
| **DB** | Compose `postgres` (or SQLite) | No app container in Compose |
| **Worker** | — | **None** in-repo |
| **Cron** | OpenClaw Gateway + `skills/*` | Digests / interview remind **outside** gotit; API only stores prefs + can run `install-cron.sh` |

Harness / gold scripts (`scripts/run_harness.py`, …) are **dev/CI**, not learner runtime.

## Stack

| Layer | Choice |
|-------|--------|
| Runtime | Python 3.12 · **uv** · FastAPI · MCP (`gotit-api` / `gotit-mcp`) |
| Core | `gotit.core` — **framework-free** (no FastAPI/MCP imports) |
| Data | Postgres 16 (Compose) or SQLite local |
| Web | React + Vite + **npm** under `web/` |
| LLM | OpenAI-compatible (`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`); e.g. 智谱 `glm-4-flash` |
| Specs | OpenSpec · `docs/VISION.md` · `docs/adr/` · this file |
| Gate | `./scripts/gate.sh` (ruff / mypy / pytest / harness); web: `cd web && npm run build` separately |

Default API port in `.env.example`: **8787** (local overrides may use 8790).

## Layout (where to edit)

```
src/gotit/
  core/          agents, models, identity, messaging, skills;
                 verify = deterministic_gate + VerifyWorkflow (BallCustody)
  db/ops/        domain ops (day, note, claim, thread, …) — barrel `__init__`
  api/routes/    one router per subdomain + chat_orchestrator (A2A)
  mcp/           app.py + common.py + tools/* → same db.ops; server.py entry
web/src/
  pages/ChatPage   main shell (workflows embed Examine/Teach/Drill)
  store/           shell + domain hooks (useExamine / useTeach / useDrill / …)
  components/      Avatars, ModeHeader, SessionStartPanel, …
alembic/versions/  0001…0015 (… + drop unused chat_messages)
openspec/changes/  active + archive/
```

Iron laws: REST ↔ MCP parity via `db.ops`; mastery **gate is deterministic code**, never LLM.

Messages: companion uses `threads`/`messages` only (plan-item `chat_messages` removed).

**Notes → claims (truth):** Web / bootcamp / MCP `gotit_ingest_note` call
`POST /v1/notes/{id}/ingest` (Compass when `LLM_API_KEY` set, else stub extract
→ `db.ops.ingest_note` + optional plan items). Legacy `POST /v1/ingest` and MCP
`gotit_ingest` remain **material→one stub claim** (response may carry
`LoopState`); **not** the product ingest path — no Web caller.

## Agents (UI nicknames)

| id | UI | Role |
|----|-----|------|
| axiom | 章鱼哥 | Examiner |
| compass | 海绵宝宝 | Curator / claims |
| echo | 派大星 | Teach-back |
| sage | 桑迪 | Project drill / interview |
| critic | 凯伦 | Independent recheck |

## State boundaries (state-boundary-tighten)

Mastery **row** write: `db.ops.write_mastery_outcome` only. Verify orchestration:
`finalize_examine_with_gate` (Critic + gate + trajectory + graph). Calibration
skips Critic/gate but still uses the writer (`source=calibration`) + light
trajectory. Companion `start_*` is **prepare only** (open-* CTA; may add a
PLANNED plan row) — does **not** set claim `IN_PROGRESS`. Thread verify REST +
MCP share `api.verify_attempt.run_verify_attempt`.

Practice kinds (not one ORM): `examine` | `teach` | `drill` | `calibration` ×
phases `prepare` | `closed`. Drill remains prep-only (no mastery). Chat is an
entry, not the mastery source of truth.

Memory write model:

| Fact | Authority | memory_entries role |
|------|-----------|---------------------|
| mastery / next_review | ClaimRow | — |
| structured fail / confuse | fail_events / graph_edges | trajectory = audit |
| failure_digest | derived cache | push + lesson tip (upsert fill follow_up) |
| bootcamp / prefs / note / event / shell | memory OK | product / user |

`prior_failures` / due fail severity / Brief「曾挂过」: trajectory `owe_next`
counts only. Graph / obs node sizing uses `fail_event_count` (= `fail_events`
rows for almost|owe_next); meta keeps alias `fail_count` for older UI.
`/v1/today` adds `mastery_snapshot` + plan-item `due_reason_*`;
interview_focus / bootcamp carry `lane`.

REST/MCP claim-close entries share `api.verify_finalize.finalize_claim_by_id`
(load claim → `finalize_examine_with_gate`). No `apply_examine_result` stub.

Active change: `openspec/changes/state-boundary-tighten/`.

Five-question check (after this tighten):

1. Why practice today? — due_reason on due + plan items; lanes for interview/bootcamp.
2. Practice lifecycle? — prepare (companion open-*) vs closed (finalize / calib writer).
3. Multiple gate writers? — verify → finalize only; calib explicit source; no
   binary `apply_examine_result`; routes/mcp use `finalize_claim_by_id`.
4. Memory dump? — digest is cache; claim/graph authoritative for mastery/fail structure.
5. New learning mode? — prepare CTA + finalize/writer; do not fork mastery write.
6. Fail counts? — schedule/Brief = trajectory owe_next; graph = fail_event_count.

## Shipped capabilities

- **Chat threads** + @mention routing + **A2A handoff** (`ChatTurn.handoff_to`, ball custody `stage=chat`)
- **Daily verify brief**: empty chat / empty thread show **owed only** —
  `due_claims` from `/v1/today` ∪ today's unverified plan items with a claim
  (one-tap 开考 / 回讲). Notes with claims are library availability — **not**
  titled「欠」and do not alone open the brief (账清 empty state instead).
  Each owed due-row shows quiet `due_reason_text`
  (why today — overdue / almost / scheduled / confuse / depends / queued;
   templates include fail-count hints when relevant); plan-open rows without a
  due reason say「今日计划」. Examine picker may still list notes for optional
  practice. When interview ramp is light/warm/urgent and prefs on, `/v1/today`
  also carries `interview_focus` (quiet/featured drill hint + `open_drill`) so
  empty chat can one-tap 深挖 without rewriting ramp tiers
- **Chat plan grounding**: each companion turn gets today's `plan_items` skeleton
  (Asia/Shanghai); ask-plan replies are enforced as short opener + exact markdown
  list (no paraphrased times/items in the opener)
- **Companion builtin tools** (whitelist, not full MCP): chat turns with an LLM key
  inject `get_today` / `list_due_claims` / `start_examine` / `start_verify` /
  `start_drill` / `get_failure_lessons` / `add_memory` /
  `get_upcoming_interview` / `close_day` via `api/companion_tools.py` →
  `db.ops`; calls land on agent message `metadata.tool_calls` (name /
  args_digest / ok / summary; `start_examine` / `start_verify` / `start_drill`
  attach `open_examine` / `open_teach` / `open_drill` + message-level lift).
  `list_due_claims` / examine finalize also fill `metadata.action_blocks`
  (owed / verdict cards, cap 5) for one-tap 开考·回讲·深挖·再练 in the bubble.
  Chat bubbles show a quiet tool trail; one-tap「开考」→ `/v1/examine`,
  「回讲」→ `/v1/teach`, 「深挖」→ `/v1/drill/sessions` (same paths as
  workflow UIs). Stub (no `LLM_API_KEY`) skips tools and does not fake writes.
  Prepare-only tools do not run Critic/gate/Sage. REST + MCP
  `gotit_post_message` share `chat_orchestrator` (same tools).
- **Day close ritual**: `POST /v1/days/today/close` + MCP `gotit_close_day` +
  companion `close_day`; `/v1/today` exposes `day_closed` / `close_summary`;
  empty chat soft-hides strong 开考 CTA after close (quiet「继续练」remains)
- **Workflows in ChatPage**: 考我 / 回讲 / 项目深挖 (embedded pages; entry in
  conversation top bar). **过门写回** only on examine + claim-bound teach
  (+ thread/MCP claim-close via `verify_finalize`). Drill finishes the
  session (`finish_drill_session`) — prep / interview practice, **not**
  mastery close.
- Library = left **drawer overlay** (notes / projects only)
- Composer: agents/skills behind `+` tray; type `@` to switch sticky
  companion (strip token, no `@` in body); quiet Apple select; active skill
  shows as a clearable chip on the composer meta row
- Chat reading column centered (~720px); thinking toggle is quiet text (not a
  pill); workflow bar hint + ModeHeader「正在…」context
- **Settings** (conversation top-right account): **我 / 提醒 / 高级** —
  profile + resume + interviews（临近备考提醒）; 提醒 = digest cron/prefs;
  高级 = Skills + MCP. **动态** is a top-bar surface (beside 弱点图谱), not a
  Settings tab — list / promote / delete shell_event+interest
  (`DELETE /v1/shell/activity/{id}`, `POST /v1/shell/activity/delete`).
  Apple plan sync is a one-liner under 我.
- **Harness API** (dev/CI, not a Settings tab): `POST/GET/PATCH /v1/harness/runs`
  runs `dev`/`gold` + human `adopt|observe|reject` in `summary` (no auto prompt
  change); CLI `scripts/run_harness.py` remains. Run `summary` contract keys:
  `total`/`passed`/`failed` plus `gate_consistent` / `routing_ok` /
  `no_spurious_write` / `failure_hook_ok` (bool rollups from case
  `metrics.rollup`; vacuous True if no tagged case). Dev cases deepen gate
  signals, `check_routing`, stub no-fake-write, failure digest→budget inject
  (no real `LLM_API_KEY`). `GET ?decision=` filters audit decisions.
  **Eval loop**: offline case → harness run → fixed metrics → human
  adopt|observe|reject (audit only; VISION P5 — holdout before adopt;
  adopt ≠ auto-apply prompt/skill).
- Nav rail = brand + library + threads (no account footer)
- Conversation top-right: **弱点图谱** opens **in the main column** (keeps
  left threads + top bar; not fullscreen) — claim 可开考/回讲/深挖；边可解释
  易混/跨主题/前置；筛选薄弱|近14天|全部（verify-derived，非百科 KG）
- **Verify loop**: examine → critic recheck → deterministic gate → trajectory / SR weighting
  + mastery-graph writeback (`fail_events`, `confused_with` edges)
  + Critic may bind a distinct OpenAI-compatible model via
    `agent_identities.llm_config` (`model` / `base_url` / `api_key_env`) or
    `CRITIC_MODEL` / `CRITIC_BASE_URL` / `CRITIC_API_KEY` (fallback: global `LLM_*`)
  + Shared finalize (`api/verify_finalize.py`) for **thread verify, `/v1/examine`,
    `/v1/teach` (claim-bound), and MCP `gotit_examine` / `gotit_teach` /
    `gotit_start_verify`** claim-close — same Critic + gate + trajectory path
    (REST↔MCP parity). Mastery row via `write_mastery_outcome`; thread verify
    REST/MCP share `run_verify_attempt`. Calibration answers use the same writer
    with `source=calibration` (no Critic/gate).
  + **Gate signals** (deterministic): after stricter-of-two, `score < 0.4` or
    provided empty/short `evidence` (<8 chars) downgrades `passed` → `almost`
    (`GateResult.signals`; never upgrades). `None` = not provided (stubs OK).
  + **ContextBudget** (`core/context_budget.py`): compose graph + failure-lesson
    blocks with per-block + total char caps; trim lessons first; wired in
    `axiom.build_prompt` **and** `build_topic_prompt` (same trim-lessons-first)
  + **Spaced review** (`core/schedule.py`, deterministic — never LLM):
    `passed` clears due; `almost` stays due today; `owe_next` →
    `next_review_at = as_of + min(30, 1+2×prior_failures)`;
    `due_claims` / fill-from-queue sort by overdue → unmet-`depends_on` demote →
    fail severity → confuse weight;
    `/v1/today` due items carry `due_reason_code` / `due_reason_text`;
    re-examine injects top `confused_with` + unmet `depends_on` short labels
    (budgeted)
  + **depends_on** (light directed edges on `graph_edges`, out-degree ≤3):
    REST `/v1/claims/{id}/depends-on` + MCP `gotit_add/remove/list_depends_on`;
    obs graph + 弱点图谱 show dashed directional prereq edges
  + **Form follows claim** (VISION P3): `claims.preferred_check_mode`
    (probe|drill|apply|teach_back; null→probe); deterministic
    `core/check_routing.py` picks CTA / open-*; DailyBrief + action_blocks +
    companion `start_verify` route to 开考 / 回讲 / 深挖; APPLY and drill-without-
    project degrade to probe; open_drill still **prep-only** (no
    `verify_finalize`); examine/teach gate path unchanged; ingest may suggest
    teach_back/drill via light heuristics
- **Cold-start calibration** (`core/calibration.py` + `db.ops.calibration`):
  CAT-lite (2PL info + adaptive θ + knowledge rotate + early stop ≤10);
  binary self-check (no Critic); correct→`passed`, incorrect→`almost` +
  `fail_event(reason=calibration)` + calibration-only confuse seed;
  REST `/v1/calibration/*` + MCP `gotit_calibration_*` + synthetic replay;
  empty chat CTA「先摸底一下」when owed empty but claims exist
  + **Item param writeback** (deterministic): gate / calib binary outcomes
    update `claims.calibration` difficulty↑ on fail / ↓ on pass, discrimination
    by surprise vs P(correct|θ=3); step shrinks with √(n+1); wired in
    `finalize_examine_with_gate` + `answer_calibration` (counters
    `n_attempts` / `n_passed` / `n_failed`)
- **First-pass bootcamp**: empty library (`claims==0`, few notes) SessionStart
  guide note→claim→开考/摸底→quiet celebrate; memory `bootcamp` status
  (done/skipped/in_progress); `/v1/today.bootcamp` + `PUT /v1/bootcamp`;
  skip once, no re-nag; has-data users undisturbed
- **Verify surface**: examine agent turns show quiet mastery chips（过了 / 还差点 /
  欠着下次；主题考完另标）；chip 读 `metadata.verdict`，不解析气泡文案
  + **VerifyTrajectory** 考→核→门 step row from `examine_verdict` /
    `recheck_verdict` / `gate_verdict`
  + **VerifyDoneBar**（session done）：gate.reason + writeback 排程影响一行 +
    「回今天」（almost 另有「接着练」）；离开工作流后 Brief/账清反映最新 owed
- **Workflow turns in thread**: examine / teach / drill optionally append to the
  active companion `messages` stream (`metadata.workflow`); Chat shows quiet badges
- Notes → claims → plan via **`/v1/notes/{id}/ingest`** (see Layout note);
  compose/view-note「出题」shows in-modal generating → ready with「去开考」
  (first claim → examine); project + resume-driven drill (resume import =
  projects + `ResumeRecord` only — **no** auto quiz notes); memory; skills;
  harness（个人 gold 对照见
  `openspec/changes/archive/2026-07-30-companion-tools-and-schedule/notes-gold.md`：
  `uv run python scripts/run_gold_compare.py`）
- MCP tools mirror chat/verify/day/skills/connectors/… (see `mcp/server.py`)
- **Mastery graph** (Postgres edges, no RAG): fail → confuse growth; optional
  `depends_on` prereq edges; budget subgraph injects into Axiom; top-bar
  「弱点图谱」opens **in the main column** (`cytoscape` + fcose — keeps left
  threads + top bar, **not** a separate fullscreen route); `/v1/obs/graph`
  enriches meta (`claim_id`, `recent`, `cross_topic`, `unmet`,
  `preferred_check_mode`, …) for launch + explain —
  `openspec/changes/mastery-graph-deepen/`

## OpenClaw shell (not in gotit core)

- WeChat channel + MCP mount: `docs/openclaw-wechat.md`；skill `skills/gotit/`
- Plan digests（早=当日计划 / 晚=今日复盘+明日询问；资讯独立默认开·20:00）:
  `docs/openclaw-digest.md`；skill `skills/digest/` + Gateway cron（Asia/Shanghai）
- **Bridge writeback**：digest → `shell_event`；「有用」→ `interest`；
  interest → `POST /v1/shell/interests/{id}/promote`（1–3 可考 claim + 今日
  plan；空话拒；幂等；MCP `gotit_promote_interest`）；顶栏「动态」一键「变成可考」
  + 删除（`DELETE /v1/shell/activity/{id}` / `POST …/delete` /
  MCP `gotit_delete_shell_activity`）；prefs `/v1/shell/digest-prefs` +
  `POST /v1/shell/digest-cron/sync`；obs `/v1/shell/*` + `/v1/obs/profile|graph`；
  Settings「提醒」+ 顶栏「动态」
- **Apple plan bridge**（P1d）：Reminders ↔ `plan_items`（`due_time`；upsert/delete
  自动 sync；早推 import→push reconcile）；`gotit.bridge.reminders` + `skills/apple-plan/`
  （osascript；**不**进 `gotit.core`）
- **Apple interview calendar**（P3d+）：面试 upsert/patch/delete → Calendar「面试」
  （标记 `[gotit-interview:<uuid>]`；完成/取消则删）；`gotit.bridge.calendar` +
  `skills/apple-interview/`；`GOTIT_SKIP_APPLE_SYNC=1` 可跳过
- **Interviews**（P3d + P4）：`InterviewEvent` + REST/MCP due-reminders；
  countdown ramp（deterministic `ramp_tier`：silent/light/warm/urgent；
  light/warm 低频 nudge + `last_ramp_nudge_at` 去重；prefs 可关）；
  Settings「我」列表 +「备考提醒」开关；companion `get_upcoming_interview`；
  今日简报 `interview_focus` 与 ramp 粘合（prefs 关则无偏置条）；
  投递 `skills/interview-remind/`（offset + ramp 同 cron）
- **Failure → 再练**（P2/P4）：`almost|owe_next` → `failure_digest`（同 claim+verdict
  去重；`passed` 不写）；`skills/failure-digest/` 可推微信；再 examine /
  claim-bound teach 经 `select_failure_lessons` + `budget_failure_lesson_block`
  注入（同 claim → confuse 邻 → 同 topic；≤3 条 / ≤600 字）；ops
  `failure_writeback_and_lessons` 供 harness；DailyBrief `failure_hint` 短提示不
  替代注入块；排程三档见 `schedule.py`（passed 清 due / almost 当日 /
  owe_next +min(30,1+2×fails)）
- **Voice teach / coding**（P3c/P2）：应用内回讲支持录音转写（`STT_*` / `LLM_*`）或
  纯文本；claim 关闭走共享 finalize；OpenClaw skills `voice-teach` / `coding` 仍可用

## Not done yet (honest)

- **Now (product UX):** main-path friction converge
  (`openspec/changes/main-path-converge/`)
- Retire or clearly deprecate legacy `POST /v1/ingest` + MCP `gotit_ingest`
  stubs (+ `LoopState` only used there) once no external callers remain
- Harness holdout UI / auto-adopt still out (metric rollups shipped in API/CLI)
- Drill ↔ mastery: either wire claim-close through `verify_finalize`, or keep
  drill explicitly **prep-only** in all user-facing copy (code today =
  `finish_drill_session` only — **no** `verify_finalize`; ingest no longer
  auto-tags project claims as drill)
- Full APPLY verify workflow (**removed from public PATCH preferred modes**;
  legacy `apply` in DB still resolves → probe via `check_routing`)
- Broad per-agent multi-model binding beyond Critic (Axiom/others still share
  global `LLM_*`; Critic may use `identity.llm_config` or `CRITIC_*`)
- Broad agent-as-tool beyond the companion **builtin whitelist** + optional user
  MCP connectors (**not** auto-mounting the full gotit MCP catalog into chat —
  not a near-term goal)
- Rich profile / full KG store beyond mastery confuse + light `depends_on`
- User-facing harness holdout UI (API/CLI only; Settings tab was wrong surface)
- Auto prompt/skill register on harness `adopt` (decision is audit-only today)
- Dedicated LLM holdout case set beyond `dev`/`gold` matrices
- Compass LLM auto-tag of `preferred_check_mode` (ingest heuristics only)
- Item-param update using per-learner θ (v1 uses fixed θ=3 surprise reference)

## Commands

```bash
uv sync --all-extras
cp .env.example .env          # set GOTIT_API_KEY + LLM_*
docker compose up -d postgres
# or: DATABASE_URL=sqlite+aiosqlite:///./gotit.db
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
