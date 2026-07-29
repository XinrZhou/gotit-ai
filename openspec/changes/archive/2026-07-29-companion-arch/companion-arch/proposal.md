# Companion-arch — 把 gotit 重设计为带人格的学习搭子

> **Status: implemented 2026-07-29**（已合并原 `companion-nav`、`a2a-handoff`）。

## Why

gotit-ai 当前形态是"验证流水线"：`core/agents/*.py` 是无状态结构化输出函数、被 API 同步 `await run_*()` 调用；`core/agents/deps.py` 的 `MemoryReader` 只读、无 `MemoryWriter`；`core/loop.py` 是纯内存空壳 `VerifyLoop`，从未被路由真正驱动。这套架构是为"验证引擎"选型的，但产品愿景是**日常学习搭子**——一个有持久人格、记得你、会互相搭话、能在需要时拉你进验证流程的陪伴体。形态与愿景冲突，需架构层重设计而非局部优化。

参考 clowder-ai 的平台层思想（身份 / A2A 通信 / 共享读写记忆 / 确定性纪律），但**不照搬其"猫群聊天室"形态**：gotit 的多 agent 应长得像"带 critic 的学习搭子"，verify-loop 降级为搭子可触发的一个工作流，而非整个产品。深度来源是 agent 架构（持久身份、A2A、读写记忆、确定性 gate），不是语言——故 Python 后端 + React 前端演进，不重写语言。

同日迭代曾拆出 `companion-nav`（四模式 → chat-first 两栏）与 `a2a-handoff`（agent→agent 链式接力）。二者本就是本变更「对话面 + messaging」的自然续篇，现并回本变更归档，避免碎片化。

## Scope

### In

- **Identity 层（新）** `src/gotit/core/identity/`：持久人格 agent = personality prompt + 稳定 rubric（复用并扩展 `db/ops/prompt.py` 版本管理）+ 每 agent 记忆命名空间。新表 `agent_identities`。
- **Messaging 层（新）** `src/gotit/core/messaging/`：threads / messages / @mention 路由 / ball-custody handoff。新表 `threads`、`messages`、`ball_custody`。
- **Agent runtime（重写）** `src/gotit/core/agents/`：从无状态函数升级为运行时实体——加载身份、读写记忆、收发 A2A 消息、产出结构化输出。
- **Memory 层（扩展）** `deps.py` + `db/ops/memory.py`：新增 `MemoryWriter`；kinds：`decision_log` / `lesson` / `evidence` / `trajectory`。
- **Verify-loop（重写）** `core/loop.py`：持久化 ball-custody 状态机；**mastery gate 是确定性代码**；recheck 由 critic 执行。
- **A2A 接力**：`ChatTurn{text, handoff_to, reason}`；一轮内链式 agent→agent（`MAX_A2A_TURNS`）；自由 chat 用 ball 记「当前搭子」。
- **对话面 API + 前端**：`api/routes/chat.py`；ChatPage；chat-first 两栏导航（资料抽屉 + navRail + 对话）；工作流内嵌专页。
- **VISION / AGENTS / openspec config** 同步为学习搭子叙事。
- **REST/MCP parity** + **测试 + gate**。

### Out（本变更不做，后置）

- agent 自主调用 MCP 工具真跑（结构已留位）
- 多用户 / OAuth；语音 / 跨平台频道适配器（OpenClaw）
- 知识图谱；完整 SM-2；approval-hub
- 暂不把 verify/teach/drill 回合写回 thread messages

## Non-goals

- 不做 clowder 的陪伴卖萌 / 游戏模式——人格服务于学习判定与陪伴感。
- 不重写技术栈语言。
- 不让 LLM 当 gate judge；handoff 有硬上限，禁止自环。

## Verification

- `./scripts/gate.sh` 全绿。
- P1：建 thread → @mention → 记忆读写 → 历史回放。
- P2：verify-loop ball-custody + 确定性 gate + critic recheck。
- P3：trajectory + SR 间隔增长。
- P5：handoff_to bypass → `agent_messages` ≥ 2，ball 持棒更新。
- 前端：`npm run build`；默认两栏；资料抽屉；空态主 CTA。
