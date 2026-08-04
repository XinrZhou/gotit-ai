# 架构评审 — AI Engineering 深度

> 视角：AI Application Engineer 面试官 · Principal AI Engineer · Agent 系统架构评审。  
> 范围：判断 gotit 如何成为有竞争力的 **AI Agent Application** —— 不是聊天机器人。  
> 产品北星：长期技术成长陪伴  
> （`用户状态 → 学习协助 → 能力评估 → 长期记忆 → 持续反馈`）。  
> 日期：2026-08-03。依据 `docs/SYSTEM.md`、`PRODUCT.md`、`VISION.md` 与已上线  
> verify / memory / harness 设计 —— 非逐行代码审计。  
> **现状补充：** Agent Runtime V2 **Phase 0–3 已落地**（Replay/Holdout、Snapshot、  
> EvidencePack、薄 Verify 信封）。详见 `agent-runtime-roadmap.md`、  
> `ai-engineering-story.md`。

---

## 结论（一屏）

**归类：** 带 **LLM Workflow 脊柱** 的 Agent Application —— 不是 Chatbot Wrapper；不是开放 Multi-Agent System。

**竞争优势：** 不是「聊天里能调工具的 Agent」，而是 **可审计的掌握状态机** —— LLM 出证，代码持真相。

**已上线的最硬 AI Eng 地板：** LLM 不能单方面过掌握门，也不能污染写回路径。

**最大 AI Eng 缺口：** 可靠性 harness 证明「我们不污染状态」；仍缺证明「教得更好了」的闭环（学习者成效 → Agent 策略）。

---

## 1. Agent 架构

### 分类

| 标签 | 贴合度 |
|------|--------|
| Chatbot Wrapper | 否 |
| LLM Workflow | 是 — 核心脊柱 |
| Agent Application | 是 — 产品形态 |
| Multi-Agent System | 部分 — 角色分工，非开放协作平台 |

**原因：** 多名 Agent、A2A 交接、companion 工具白名单，都坐在 **产品定义的 Verify Workflow** 上。自主度刻意短；状态迁移才是真正的「Agent」。

正确面试表述：

> 固定 verify 脊柱上的角色分工 Agent。

错误表述：

> 我们有五个角色，所以做了 Multi-Agent 系统。

### 维度记分卡

| 维度 | 现实 | 深度 |
|------|------|------|
| **Planning** | 分解主要在产品逻辑：欠练队列、计划项、`check_routing`、CAT、间隔复习。Companion 不发明多步学习计划。 | 规划「练什么」；几乎无 Agent 自规划 |
| **Execution** | Companion 工具多为 **prepare-only**（开考 / 回讲 / 深挖）。掌握闭环走 finalize。 | 半自主：能行动，不能单独关掌握 |
| **Tool Calling** | 真：内置白名单 → `db.ops`；MCP 给 OpenClaw；全量 MCP **不**自动挂进聊天 | 受控能力，不是开放工具汤 |
| **State Management** | 强：claim / 掌握 / ball custody / day_closed / owed / prepare vs closed | 「Agent 感」的主来源 |
| **Reflection** | Critic 复核 + `deterministic_gate`（双人取严；分数/证据只能降级）。不是自由 ReAct 自省环 | 跨角色复核 + 代码终审 |

### 架构图（概念）

```text
学习者表面（Chat / 工作流 / MCP host）
        │
        ▼
Companion Agents（身份 + 工具 + 交接）
        │  prepare / 叙述 / examine / teach
        ▼
Verify 脊柱：EvidencePack → Axiom → Critic → WriteIntent
        │              → deterministic_gate
        ▼
单一掌握写路径（write_mastery_outcome）+ run_id 审计
        │
        ▼
跨日学习者状态（claims、排程、失败图、digest）
        ▲
Replay / Holdout（gate.sh）锁契约
```

---

## 2. Memory 架构

**不是** 仅靠对话历史。  
**是** 以 claim 为中心的长期学习者状态；聊天是入口，不是真相源。

| 能力 | 有无 | 形态 |
|------|------|------|
| 用户画像 | 轻 | resume / prefs / bootcamp / interview — 非厚心理画像 |
| 技能状态 | 有（核心） | claim 掌握、`preferred_check_mode`、due / `next_review_at` |
| 知识状态 | 有 | notes → claims；权威在 claim 行，不在聊天摘要 |
| 历史经验 | 有 | fail_events、trajectory、failure_digest、confuse 边 |
| 成长跟踪 | 有（可解释） | 间隔复习、掌握图、CAT 题参、Brief `due_reason_*` |
| 派生投影 | 有（Phase 2） | `LearnerStateSnapshot`；verify 侧 `EvidencePack` |

### 值得讲的设计

1. **权威分离** — 掌握 / 结构化失败在 claim / 图；`memory_entries` 不得成为掌握神谕。  
2. **上下文有预算** — 再练注入失败教训 + 图邻接并硬 trim（VISION P4）；verify 走 EvidencePack。  
3. **失败有用** — 失误是一等状态，服务排程与再注入，不是一次性日志。

### 诚实边界

这是 **Mastery Graph + Schedule State**，不是完整用户心智模型或开放知识图谱。对个人成长 Agent，这是正确切口 —— 不是「没做完的 RAG」。

---

## 3. LLM 可靠性

项目里最硬的 AI Engineering 切口：比多数 Agent Demo 更清晰。

### 责任切分

| 关切 | 归属 |
|------|------|
| 理解 / 生成 / 讲解 / 对话 / Critic 意见 | LLM |
| 掌握档 / 排程 / 写回 / CTA 路由 / 题参更新 | Code |
| 权威持久化 | `write_mastery_outcome` / 共享 finalize |
| 提案装信封 | WriteIntent（无写权直至 Gate 接受） |

### 防腐机制（工程，不是 prompt 戏）

- **Gate 是确定性代码，永不交给 LLM**（VISION P7）。  
- Critic 不能单方面过关；低分 / 空证据 **只能降级**。  
- Companion 工具：**prepare ≠ 掌握写**；无 `LLM_API_KEY` 的 stub 不假写。  
- Harness 契约含 `no_spurious_write` / `gate_consistent` 等；**replay + holdout 进 CI**。  
- REST ↔ MCP 共享 `db.ops` + 同一 finalize —— 降低双路径漂移。

**判断：** LLM 管生成；代码管真相。  
剩余风险是 **上游生成效度**（探针是否真测该 claim）—— 不是失控状态突变。那是下一层，不是未完工的地板。

---

## 4. 评测体系

| 类型 | 状态 |
|------|------|
| 规则型 | 有 — gate、排程、路由、gate 信号、CAT 参数 |
| LLM 评判 | 有 — Critic 是 **顾问**，不是终审庭 |
| 用户反馈 | 有 — 掌握芯片 / Done 条 / harness `adopt\|observe\|reject` |
| 质量指标 | 部分 — harness 离线 rollup；线上学习者成效环弱 |
| 契约回归 | **有（Phase 1）** — Replay + Holdout + `suite_version` |

### 已买到什么

「系统会不会污染掌握？」变成 **可回归契约** —— Agent Application 少见成熟度。

### 缺席的代价

1. **安全 ≠ 有效** — gate 一致不证明学习者被教会。  
2. Adopt 仍仅审计 — 演进有纪律，尚无证据驱动的自动加强。  
3. 硬面试题未答：*你怎么知道上月 Axiom 变强了？*

---

## 5. 与 clowder-ai 的设计思想对照

参考：[clowder-ai](https://github.com/zts212653/clowder-ai)。  
**不做功能清单。不做代码对比。** 只比设计意识形态。

| | Clowder | Gotit |
|---|---------|-------|
| 北星 | 把孤立模型变成 **协作团队** 的平台 | 把「感觉流利」变成 **可排程掌握态** 的 verify 环 |
| 地板口号 | 模型定天花板；平台定地板 | Verified = done；Gate 是代码 |
| 记忆 | 共创用的机构证据 / 教训 / 决策 | 成长用的 claim / 失败 / 排程权威 |

### 值得借鉴

1. **三层切分** — 模型推理；平台持记忆、纪律、身份。  
2. **稳定人格服务稳定判断** — 角色是 rubric 锚，不是 cosplay。  
3. **证据即机构记忆** — fail→lesson→再考 与共享教训 / 决策日志同族。  
4. **Adopt 前先评测** — prompt/skill 改动要有 holdout 证据（VISION P5）；已向显式契约推进。  
5. **硬轨在代码** — 铁律由系统执行，不靠模型听话。

### 不要照抄

1. **开放 Multi-Agent 协作平台** — gotit 域是掌握，不是「想法→产品」团队 OS；照抄稀释 Verified = done。  
2. **默认拉高 Agent 规划自主度** — 与「不为自主而自主」的产品立场冲突。  
3. **把自我进化当英雄故事** — 先长学习者状态；Agent 自改进是次要。  
4. **「笨系统 + 聪明 Agent」开放检索当掌握权威** — gotit 需要代码持有过关真相。  
5. **CVO / 共创团队隐喻** — 学习者需要诚实考官 + 稳定陪伴，不是软件猫班底。

---

## 6. 终评

### 最有价值的技术故事（一句）

**经「LLM 出证 → Critic 复核 → 确定性 Gate → 单一掌握写回」的 verify 脊柱，gotit 把无状态生成器变成跨日、抗污染的学习者掌握状态机 —— 聊天是壳，掌握是真相；Replay/Holdout 与薄信封把这一地板做成可 CI 回归的工程。**

### 最大技术短板（AI Engineering，不是功能洗衣单）

**缺学习者成效 → Agent 策略的度量闭环。**

离线 harness 能证明 *我们不污染状态*，但不能持续回答 *教得是否更好* —— 探针效度、check-mode 路由质量、教训注入是否提高再过率，尚未成为驱动策略 / prompt 演进的线上证据。

那是：

- 高度自律的 verify-workflow 产品，与  
- 能 **证明自己在变强** 的成长 Agent Application  

之间的鸿沟。

---

## 竞争路径（守住铁律）

不可削弱：

- Gate 留在代码。  
- 掌握留在权威状态。  
- Agent 边界清晰（prepare vs finalize）。

下一刀：

> 把 harness 从 **防腐** 扩到 **防无效** —— 把留存 / 再过 / 清欠信号绑回路由、注入预算与考官 / Critic 策略。

这才是把 gotit 从聊天机器人和通用 Multi-Agent 平台里拉开的 AI Native 故事。  
（Phase 4 的 ToolSpec / Trace 是打磨，不是这条主论点。）
