# Gotit AI — 项目代码事实基线

> 角色视角：Staff AI Application Engineer / Principal Engineer / AI Agent 系统架构师  
> 范围：基于仓库代码与 `docs/SYSTEM.md` 的事实盘点  
> 不含：产品市场价值、PMF、商业化、未来改造方案  
> 日期：2026-08-03

---

# 1. 项目整体定位

**当前系统本质：**

一套以 **可考知识点（Claim）为掌握权威**、以 **确定性门控（deterministic gate）为终审** 的个人技术成长状态机；LLM 多角色（考 / 整理 / 回讲 / 深挖 / 复核）负责出题、评判草稿与陪伴对话，**掌握写回不交给单一模型**。

从 AI Application 工程视角，它是：

| 维度 | 事实 |
|------|------|
| 应用形态 | 单用户 Companion SPA + FastAPI + MCP（OpenClaw 外挂渠道） |
| AI 用法 | 结构化输出 Agent（pydantic-ai）+ 聊天 Tool whitelist + 固定 Verify 流水线 |
| 核心闭环 | 资料 → Claim → 考/回讲 → Critic → 代码 Gate → 排程 / 失败图写回 |
| 非核心 | 聊天是入口与壳；Drill / 深挖明确 **不过门** |

一句话：**Verification-centric learning OS**（验证型成长运行时），不是问答 bot，也不是开放式自主 Agent 平台。

---

# 2. 系统架构分析

## Frontend（`web/`）

| 项 | 事实 |
|----|------|
| 技术职责 | React + Vite SPA；只打 REST API，不直连 MCP |
| 用户交互 | `ChatPage` 为主壳：空态今日简报 / 欠练、线程聊天、工作流嵌入（考我 / 回讲 / 深挖）、弱点图谱、Settings |
| AI 交互入口 | Composer 发消息 → chat REST；`@` 切 sticky companion；工作流走 `/v1/examine`、`/v1/teach`、`/v1/drill`；气泡内 tool trail / action blocks 一键开练 |
| 状态 | 单一 `StoreProvider`：`useShell` / `useWorkspace` / `useExamine` / `useTeach` / `useDrill` … |

## Backend（`src/gotit/api` + `db/ops`）

| 项 | 事实 |
|----|------|
| API 设计 | 按子域拆 router（chat / day / notes / claims / examine / teach / drill / calibration / memory / shell / harness …）；Bearer 单用户 |
| 业务逻辑 | 领域写在 `db/ops/*`；路由与 MCP **共用** 同一 ops；`gotit.core` 无 FastAPI/MCP import |
| 编排层 | `chat_orchestrator`（A2A 接力）、`verify_finalize`（Critic+gate+写回）、`companion_tools`（聊天工具白名单） |

## AI Service

| 项 | 事实 |
|----|------|
| LLM 调用 | `core/agents/llm.py`：`OpenAIChatModel` + OpenAI-compatible endpoint（`LLM_*`）；Critic 可叠 `CRITIC_*` / identity `llm_config` |
| Prompt 管理 | `prompts/*.md`（frontmatter）→ `PromptVersion` 入库；identity personality + 可选 rubric；Skills 为按需注入片段 |
| Agent 调用 | pydantic-ai `Agent` + `output_type`（ExamineVerdict / ChatTurn / …）；无 key 时 stub |

## Agent Layer

| Agent | 代码角色 | 触发 |
|-------|----------|------|
| axiom | 考官，多轮 `ExamineVerdict` | examine / topic examine |
| compass | 笔记 → claims | note ingest |
| echo | 回讲评判 | teach |
| sage | 项目/面试深挖 | drill |
| critic | 独立复核 | finalize 路径 |
| runtime `run_chat` | 自由聊 + handoff + tools | chat / MCP post_message |

**Verify 执行流（固定流水线，非开放规划）：**

```text
examine(axiom) → recheck(critic) → deterministic_gate(code)
  → write_mastery_outcome(ClaimRow)
  → trajectory / fail_events / graph_edges / failure_digest
```

`VerifyWorkflow` + `BallCustody` 管 stage 转移；`MAX_A2A_TURNS=4` 管聊天接力。

## Data Layer

| 权威 | 存什么 |
|------|--------|
| `claims` | 掌握状态、`next_review_at`、topic/tags、`preferred_check_mode`、CAT 参数 |
| `plan_items` / `learning_days` | 日计划与核销 |
| `threads` / `messages` | 对话短期上下文 |
| `fail_events` / `graph_edges` | 失败结构 + confuse / depends_on |
| `memory_entries` | trajectory 审计、failure_digest 缓存、bootcamp/prefs/event 等；**不是**掌握权威 |
| `ball_custody` | 线程内 verify 球权 |

**无** embedding / vector store / RAG 索引（代码与 SYSTEM 均写明 mastery graph，非 RAG）。

## 架构图

```text
┌─────────────────────────────────────────────────────────────┐
│  Web (React)          OpenClaw / Skills (外进程)              │
│  ChatPage + workflows   MCP client → gotit-mcp                 │
└───────────┬───────────────────────────┬─────────────────────┘
            │ REST                      │ MCP tools
            ▼                           ▼
┌───────────────────────┐    ┌──────────────────────────────┐
│  FastAPI (gotit-api)  │    │  MCP server (thin)           │
│  routes + orchestrators│◄──►│  → 同一 db.ops               │
└───────────┬───────────┘    └──────────────┬───────────────┘
            │                               │
            ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│  db.ops（领域写）  ←→  Postgres / SQLite                       │
└───────────────────────────────┬─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│  gotit.core（framework-free）                                 │
│  agents/* · loop.gate · schedule · context_budget · graph   │
│  pydantic-ai → OpenAI-compatible LLM                        │
└─────────────────────────────────────────────────────────────┘
```

---

# 3. AI 能力盘点

| 能力 | 状态 | 代码依据 |
|------|------|----------|
| LLM 调用 | **A** | `core/agents/llm.py` `build_model` / `resolve_llm_binding`；各 agent `Agent(...).run`；无 key stub |
| Prompt 管理 | **A** | `prompts/*.md` + `prompts/__init__.py`；`PromptVersionRow`；`compose_system_prompt`；Skills 注入 |
| Agent Workflow | **A**（固定） | `VerifyWorkflow` + `finalize_examine_with_gate`；聊天 A2A `MAX_A2A_TURNS` |
| Planning | **B** | 有日计划 `plan_items`、companion 工具查计划/欠练、计划问答硬规则；**无** LLM 自主多步任务规划器 / ReAct planner |
| Tool Calling | **A**（白名单） | `companion_tools.py`：`get_today` / `list_due_claims` / `start_*` / `add_memory` / `close_day` …；可选用户 MCP connectors；非挂载全量 gotit MCP |
| Memory | **B** | `memory_entries` 分层 + trajectory / failure_digest；掌握在 Claim；聊天注入 `list_memory(layer=long, limit=10)`；非完整记忆系统 |
| RAG | **C** | 无 embedding/向量检索；再练上下文 = graph + failure lessons 预算拼接（`context_budget.py`） |
| Context Management | **A**（域内） | 线程 history≤20；memory≤10；`ContextBudget` 总长/块上限；计划骨架硬约束 |
| Evaluation | **A**（离线 harness） | `harness` API/CLI、`dev`/`gold` cases、人工 adopt\|observe\|reject；gate/routing 等确定性指标；**非**线上自动评测闭环改 prompt |

状态约定：

- **A** 已实现
- **B** 部分实现
- **C** 未实现

---

# 4. Agent 设计分析

## 是否「真正 Agent」？

按常见 Agent 五件套对照：

| 维度 | 是否存在 | 形态 |
|------|----------|------|
| Planning | 弱 / 部分 | 日计划与工具选择；无开放目标分解 |
| Execution | 有 | 工具执行 + 工作流 API + LLM 结构化轮次 |
| State Transition | 有 | Claim 掌握态、BallCustody stage、plan status、day close |
| Tool Usage | 有 | 聊天白名单 + 可选 connector；verify 路径主要是结构化 Agent，不靠开放 tool loop |
| Feedback Loop | 有且偏硬 | Critic + **代码 gate** + SR 排程 + fail graph 再注入 |

**结论：** 不是开放式自主 Agent（无长期 goal → 自行规划 → 环境探索）。

更接近：

1. **Multi-role structured LLM pipeline**（考/整理/回讲/深挖/复核）
2. **+ Chat companion with constrained tools & A2A handoff**
3. **+ Deterministic mastery state machine**

聊天侧有轻量 agentic（tool + handoff）；掌握侧是 **workflow + dual-judge + code gate**，刻意限制 LLM 终审权。

---

# 5. Memory 和 State 分析

## 存的是什么？

**两套，权威分离（代码写死）：**

| 类型 | 权威 | 角色 |
|------|------|------|
| 聊天记录 | `threads` / `messages` | 短期对话；可附 workflow 消息 |
| 学习掌握态 | **`ClaimRow`**（status / next_review_at） | 掌握唯一写口：`write_mastery_outcome` |
| 失败结构 | `fail_events` + `graph_edges` | 易混 / 前置 / 图可视化 |
| memory_entries | 辅助 | trajectory 审计、failure_digest 缓存、bootcamp/prefs/event；digest 非掌握权威 |

## Short-term Memory

- Chat：`MessageReader` 最近约 20 条 + 当轮 user text
- Examine：多轮 history dict 传入 axiom prompt
- Working layer：如 `failure_digest`、聊天事件记忆

## Long-term Memory

| 期望项 | 现状 |
|--------|------|
| 用户画像 | **弱**：prefs / resume / interviews / shell interest；无完整 learner profile 模型 |
| 技术能力 | **Claim 级掌握 + CAT θ 校准（冷启动）**；非连续技能树评分卡 |
| 历史学习 | notes / claims / plan / trajectory / fail_events |
| 成长轨迹 | trajectory + 排程间隔 + 弱点图谱；可视化有，非完整成长曲线产品模型 |

## Growth State

已形成 **Claim 粒度的掌握与复习状态机**（passed / almost / owe_next + SR），外加 confuse/depends 图与校准难度参数。

**未形成** 统一的「用户能力向量 / 技能 embedding / 跨域能力画像」——增长状态是 **知识点队列 + 失败图**，不是端到端 learner model。

---

# 6. 当前技术优势和不足

## 已具备优势

1. **掌握终审与 LLM 解耦**：`deterministic_gate` + 单一 `write_mastery_outcome`，职责清晰。
2. **双表面同域**：REST ↔ MCP 共用 `db.ops`，符合 Agent/应用双入口工程纪律。
3. **`core` 框架隔离**：领域可测；gate / schedule / check_routing / context_budget 有确定性逻辑与 harness。
4. **Verify 闭环完整度高**：双 Agent 评判 → 门 → 写回 → 再练注入（graph + lessons）链路已落地。
5. **上下文有预算意识**：再练不塞整本笔记，符合「省着给」的工程约束。
6. **角色边界清楚**：五身份 + identity/prompt 分离；聊天不误注 examine rubric。
7. **单用户部署假设一致**：auth / 数据模型与「个人系统」一致，复杂度可控。

## 当前不足（事实缺口，非建议）

1. **无 RAG / 语义检索**；相关上下文靠图邻接与手工预算，不是检索增强。
2. **Planning 停留在日计划与 CTA**，无通用多步 Agent planner。
3. **Tool 面刻意收窄**：白名单 prepare-only；Drill 明确不过门。
4. **Memory 表语义混杂**（审计 / 缓存 / prefs），长期「用户状态」分散在 Claim / graph / memory。
5. **无完整用户能力模型**（画像 / 跨 claim 技能表示）。
6. **Eval 在离线 harness + 人工决策**；adopt 不自动改 prompt（产品铁律，也是自动化缺口）。
7. **多模型绑定范围窄**：主要 Critic 可独立；其他 agent 共享全局 `LLM_*`。
8. **遗留路径仍在**：如 legacy ingest stub（SYSTEM「Not done」）。

## 需要进一步验证的问题

（仅标出未知/需实测，不给方案）

1. 真实 LLM key 下 companion tool 选择与 `open_*` CTA 的稳定率（stub 路径不测工具写）。
2. Axiom / Critic 双评判在真实答题上的一致性与 gate signal 触发频率。
3. ContextBudget 裁剪后，再练时模型是否仍能用上「曾挂教训」。
4. 长期使用后 Claim / graph / trajectory 膨胀对 `/v1/today` 与 prompt 组装延迟的影响。
5. CAT 固定 θ=3 的 item 参数写回，对个人难度校准是否足够。
6. OpenClaw 侧 digest / promote / Apple bridge 与应用内状态的一致性（跨进程）。
7. Drill「prep-only」与学习者心智模型是否冲突（产品文案 vs 实际写回边界）。
8. Harness gold 对真实模型漂移的覆盖是否够（SYSTEM 亦标 holdout UI / 专用 holdout set 未齐）。

---

# 总括

这是一个验证闭环已落到代码、分层清晰的 **AI Native 个人成长运行时**；Agent 能力集中在 **结构化角色流水线 + 约束工具聊天**，长期状态权威在 **Claim/排程/失败图**，而非聊天记录或通用 Memory 库。

---

## 主要代码锚点（便于复核）

| 主题 | 路径 |
|------|------|
| LLM 工厂 | `src/gotit/core/agents/llm.py` |
| 聊天 runtime | `src/gotit/core/agents/runtime.py` |
| 聊天编排 / A2A | `src/gotit/api/chat_orchestrator.py` |
| Companion tools | `src/gotit/api/companion_tools.py` |
| Verify finalize | `src/gotit/api/verify_finalize.py` |
| Gate / BallCustody | `src/gotit/core/loop.py` |
| 排程 | `src/gotit/core/schedule.py` |
| Context budget | `src/gotit/core/context_budget.py` |
| 掌握写回 | `src/gotit/db/ops/claim.py` → `write_mastery_outcome` |
| Memory ops | `src/gotit/db/ops/memory.py` |
| ORM | `src/gotit/db/models.py` |
| Prompt 加载 | `src/gotit/prompts/__init__.py` + `prompts/*.md` |
| 系统快照 | `docs/SYSTEM.md` |
