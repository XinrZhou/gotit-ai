# Tasks — companion-arch

按 P1→P5 顺序。`[gate]` = `./scripts/gate.sh`。原 `companion-nav` / `a2a-handoff` 任务已并入。

## P1. 搭子骨架：identity + messaging + chat 对话面

### 1.1 数据模型与 migration
- [x] `core/models.py` 加 `AgentIdentity`、`Thread`、`Message`、`BallCustody` DTO
- [x] `db/models.py` 加 4 张表对应 Row
- [x] Alembic migration `0005_companion_arch`
- [x] [gate] 现有 day ops 回归

### 1.2 Identity 层
- [x] `core/identity/` + `db/ops/identity.py` + seed（axiom/compass/echo/sage/critic）
- [x] [gate] `uv run mypy src`

### 1.3 Messaging 层
- [x] `core/messaging/` `route_message` + `db/ops/thread.py`（thread/message/ball ops）
- [x] [gate] `uv run pytest`

### 1.4 Agent runtime + deps
- [x] `MemoryWriter` / `MessageReader`；`runtime.run_chat`；Session* deps
- [x] [gate] `uv run mypy src`

### 1.5 Chat API + 前端
- [x] `api/routes/chat.py` + `identities.py`；MCP chat 工具
- [x] `web/src/pages/ChatPage/`；Mode 默认 `chat`
- [x] [gate] web build + pytest

### 1.6 P1 端到端
- [x] `tests/test_companion_e2e.py`（路由 / mention / 记忆 / 隔离）
- [x] [gate] `./scripts/gate.sh`

## P1b. 前端导航收敛（原 companion-nav）

- [x] Shell 只挂 ChatPage；移除 SegmentedTabs
- [x] 两栏：资料抽屉 + navRail + 对话；ModeHeader；工作流内嵌专页
- [x] Chat-first：自动打开最近 thread；空态主 CTA
- [x] `cd web && npm run build`

## P2. 验证工作流：ball-custody + 确定性 gate + critic

- [x] `VerifyWorkflow` + `deterministic_gate`；保留 legacy `VerifyLoop`
- [x] `prompts/critic.md` + `core/agents/critic.py` + `RecheckVerdict`
- [x] `POST /v1/threads/{id}/verify` + `gotit_start_verify`
- [x] e2e + harness `gate-no-llm`
- [x] [gate] `./scripts/gate.sh`

## P3. 学习轨迹：memory + trajectory + SR

- [x] `append_trajectory` / `list_trajectory` / `count_prior_failures`
- [x] axiom 注入 trajectory；`prior_failures` 调 SR 间隔
- [x] e2e `test_verify_trajectory_and_sr`
- [x] [gate] `./scripts/gate.sh`

## P4. skills 按需加载

- [x] `core/skills/` + `prompts/skills/{debug,review}.md`
- [x] `run_chat` skills/tools；API/MCP/前端技能选择器
- [x] `tests/test_skills.py`
- [x] [gate] `./scripts/gate.sh`

## P5. A2A 接力（原 a2a-handoff）

- [x] `ChatTurn` + `AgentReply.agent_messages` + `BallStage.CHAT`
- [x] `run_chat` → `ChatTurn` + `force_handoff`；`chat_orchestrator` 链式接力
- [x] MCP `gotit_post_message` 同步；前端多条 message + handoff 标签
- [x] e2e A2A bypass + 未知 agent；断言改 `agent_messages`
- [x] [gate] `./scripts/gate.sh`

## 收尾

- [x] `docs/VISION.md` / `openspec/config.yaml` / `AGENTS.md` 同步学习搭子叙事
- [ ] `skills/gotit/SKILL.md`：更新 MCP 工具列表（chat/workflow）— 待人工同步
- [x] 合并 `companion-nav` / `a2a-handoff` 进本变更并归档
- [x] [gate] `./scripts/gate.sh` 全绿
