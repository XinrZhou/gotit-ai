# Design — agent-rewrite

## Approach

前台人性化、后台工程化。Agent 框架用 Pydantic AI，状态机保留现有 `VerifyLoop`（闭环逻辑产品定，Agent 是节点），记忆分层共享，prompt 文件化 + DB 版本化，harness 四层覆盖 prompt/agent/loop/system。

### Agent 框架：Pydantic AI

- 选型理由：同源 Pydantic 生态（FastAPI/OpenAI SDK/现有 DTO 全是 Pydantic）、轻、多 provider、structured output 原生、agent-as-tool + 共享 deps 实现多 Agent 协作、core 层可用（非 web/transport 框架，不违反 Iron Law #4）
- 多 Agent 协作方式：程序化编排（`VerifyLoop` 调对应 Agent）+ 共享 `AgentDeps`（含 memory）。Axiom 与 Echo 是两个独立入口（`/v1/examine` vs `/v1/echo`），不互调
- provider 后选：直接用 Pydantic AI 的 model 切换（`OpenAIModel`/`AnthropicModel`），M0 默认 OpenAI，换 provider 改 settings 不改 Agent

### 3 个 Agent（M0）

| Agent | 名字 | M0 状态 | system prompt 要点 |
|-------|------|---------|-------------------|
| 考官 | Axiom | 真实 LLM | 精准、追问不立刻判、答错顺口讲、按 topic 切出题风格、输出 `ExamineVerdict` |
| 管家 | Compass | 真实 LLM | 沉静、从材料抽 claim 带 topic、排复习、每日推题（遗忘曲线 + 弱点加权） |
| 回讲官 | Echo | 真实 LLM（无 key 时 bypass） | 扮不懂的学生、追问"为什么""那如果…呢"、输出 `TeachVerdict` |

**Sage（复盘官）整个后置**：M0 只把 `memory_entries`/harness 数据存好，Sage 骨架与报告生成后续做。

### Agent 协作与状态机

- **Axiom 多轮交互**：`/v1/examine` 是**多轮端点**，不是单次请求/响应。每轮传 `claim_id` + 用户回答，后端读 `chat_messages` 历史 + 写入新消息 + 调 Axiom。Axiom 返回中间轮 `{follow_up, done: false}`（继续追问）或最终轮 `{verdict, score, evidence, follow_up, done: true}`（判定）。对话历史复用现有 `chat_messages` 表（按 `plan_item_id`，role `examiner`/`user`）。**注：独立的 `examine_runs` 留痕表本变更未建**，per-attempt trace 由 `chat_messages` + harness 两表承担；如需单独的 per-attempt 指标表可后续补。
- **Axiom 在 `EXAMINE` 状态内完成多轮追问+引导+判定**，不切 `COACH` 状态（`VerifyLoop` 的 `COACH` 状态在本变更中废弃/不使用）。Axiom 自己在 `EXAMINE` 里答错时顺口讲，最后才给 `ExamineVerdict`。
- **Echo 不走 `VerifyLoop`**：独立角色反转检验模式。入口是「回讲」按钮，走 `POST /v1/teach`，**多轮**（`TeachVerdict.next_question` 承载下一轮）。Echo 对话历史**复用 `chat_messages` 表**（按 `plan_item_id`，role 用 `echo`/`user`），和 Axiom 共享同一 claim 的历史，前端按 role 区分 Axiom 轮 vs Echo 轮。不更新 `Claim` 状态（回讲是辅助检验，不作为掌握判据）。
- **memory 读写职责**：agent 通过 `AgentDeps.memory` **只读** memory（注入 prompt 上下文），**不写 DB**。所有 DB 写（memory/examine_runs/claim 状态/chat_messages）由 `db.ops` 在 agent 返回后由编排层（routes/mcp handler）执行。这保持 `core/agents` 无副作用、core 纯净。
- 多 Agent 协作靠程序化编排（`VerifyLoop` 调 Axiom/Compass）+ 共享 `AgentDeps`（含 memory）。
- provider 切换直接用 Pydantic AI 的 `OpenAIModel`/`AnthropicModel`，**不另包 `LlmClient` 协议**（避免重复抽象）。settings 注入对应 model，agent 代码不动。

### IN_PROGRESS 回归路径

`almost` → `IN_PROGRESS` 的 claim 不设 `next_review_at`，不在回归队列。为避免它「消失」在系统里：

- `list_due_claims` 扩展：除 `QUEUED`/`NOT_YET` 外，也查 `IN_PROGRESS`（无 `next_review_at` 限制）
- Compass 推题时排序优先级：`QUEUED`/`NOT_YET`（due）> `IN_PROGRESS`（续考）> `MASTERED`（低频回归，后置）
- 前端今日队列里 `IN_PROGRESS` 的 claim 标「续考」状态，用户可继续上次没考完的

### 人性化流程

```
你贴材料/说话
  ↓
Compass 默默抽 claim 带 topic → 进今日队列（不打断）
  ↓
你说"考考我" / Compass 觉得该复习
  ↓
Axiom 开考 → 追问几轮（不立刻判）→ 答错自然引导 → 最后才说"过了/还差点/欠着下次"
  ↓
判定写入 examine_runs + 更新 Claim 状态（按映射）+ 写记忆
  ↓
（可选，独立模式）Echo 回讲：你讲它听，它提问 → 返回 teach_verdict（不走 VerifyLoop）
```

判定是连续谱：`passed` / `almost` / `owe_next`，不是二元 passed/failed。`ExamineVerdict.verdict` 字段承载。映射见下「闭环与 DTO」。

### 记忆系统（分层，SQL/NoSQL 混合）

```
memory_entries
  id            uuid pk
  user_id       varchar(64) indexed
  layer         varchar(16) indexed        -- long | working | session
  kind          varchar(32)               -- weakness | preference | note | event
  topic         varchar(64) indexed
  content       jsonb                     -- 任意结构：弱点描述/偏好/事件载荷
  source        jsonb                     -- {run_id?, claim_id?, note_id?, agent?}
  created_at    timestamptz
  expires_at    timestamptz nullable       -- long 层为 null
```

- **long**：弱点主题、偏好检验形式、长期目标（不过期）
- **working**：当前对话上下文（短期）
- **session**：跨会话事件（今天考了什么、明天该复习什么）

`content` / `source` 用 JSONB 吸收任意结构（弱点可带 score 趋势、事件可带轮次），强查询字段（layer/topic/user_id）保持关系列 + 索引，混合模式兼顾灵活与查询性能。3 个 Agent 通过 `AgentDeps.memory` **只读**；写由 `db.ops` 编排层在 Axiom/Compass 返回后追加（agent 不写 DB）。M0 实现 long + session，working 走对话内消息即可。

### 提示词管理

- 文件：`prompts/{axiom,compass,echo}.md`，git 管版本/diff/回滚
- DB：`prompt_versions(agent_name, version_label, content_hash, system_prompt, config jsonb, notes, created_at, is_active)`，`config` 存 temperature/model 等运行时配置
- register：`POST /v1/prompts/register`（REST）+ `gotit_register_prompts`（MCP）读 `prompts/*.md` → 算 hash → 写表 → 每个_agent 最新版本设为 active
- 运行时：Agent 启动按 `is_active` 取当前版本注入

### 系统级 harness（四层）

实际实现简化为两文件（runner + case set），evaluator/verdict/report 留 TODO：

```
src/gotit/harness/
  __init__.py     # Case / CaseResult / run_harness（runner，写两表）
  cases/
    dev.py        # dev case 集：prompt/agent/loop/system 四层各一 case
```

DB（两表，关系表支持按 case 跨 run 聚合）：
```
harness_runs
  id              uuid pk
  started_at      timestamptz
  git_sha         varchar(40)
  prompt_versions jsonb                     -- {axiom: ver, compass: ver, ...}
  label           varchar(64)
  case_set        varchar(16) indexed        -- dev | holdout | regression
  summary         jsonb                     -- 聚合指标 {pass_rate, avg_score, total_tokens, by_layer}
  verdict         varchar(16)               -- adopt | observe | reject
  created_at      timestamptz

harness_case_results
  id              uuid pk
  run_id          uuid fk indexed            -- -> harness_runs.id
  case_id         varchar(64) indexed        -- 跨 run 按 case 聚合用
  case_type       varchar(16)               -- material | claim | loop | persona
  layer           varchar(16) indexed        -- prompt | agent | loop | system
  passed          bool
  score           float
  metrics         jsonb                     -- {tokens_in, tokens_out, latency_ms}
  trace           jsonb                     -- 完整步骤 [{agent, prompt_version, input, output, tokens}, ...]
  created_at      timestamptz
```

- 两表而非单表 JSONB 数组：harness 最有价值的查询是「某 case 在历次 prompt 版本下的通过率趋势」，关系表 + `(case_id, layer)` 索引比 JSONB 数组展开高效得多
- `harness_runs.summary` 仍用 JSONB 存聚合指标（一次 run 一份，不需跨 run 查）
- Trace 存完整步骤（哪个 Agent / 哪版 prompt / 输入输出 / token），出问题可回放
- gate：`scripts/gate.sh` 加 `run_harness --set dev`
- M0 跑一次 baseline run 存入 DB

### 闭环与 DTO

`ExamineVerdict`（新增，多轮端点统一返回，`done` 区分中间轮/最终轮）：
```python
class ExamineVerdict(BaseModel):
    done: bool                 # False=中间轮（只有 follow_up），True=最终轮（有 verdict/score/evidence）
    verdict: Literal["passed", "almost", "owe_next"] | None  # done=True 时必填
    score: float | None        # done=True 时必填，0.0–1.0
    evidence: str | None       # done=True 时必填，引用 claim 内容说明为什么这么判
    follow_up: str             # 中间轮=下一轮追问/引导；最终轮=复习建议
```

`TeachVerdict`（Echo 回讲，独立模式，多轮）：
```python
class TeachVerdict(BaseModel):
    done: bool                 # False=继续追问，True=回讲结束
    you_taught_well: bool | None  # done=True 时必填，你教会它了吗
    gaps: list[str]            # 它还没懂的点（=你没讲清的点）
    next_question: str | None  # done=False 时必填，下一轮追问
```

**判定 → 状态映射**（`apply_examine_result` 升级为三值）：

| `ExamineVerdict.verdict` | `Claim.status` | `PlanItem.status` | `next_review_at` |
|--------------------------|----------------|-------------------|------------------|
| `passed` | `MASTERED` | `verified` | 清空 |
| `almost` | `IN_PROGRESS`（新） | `in_progress` | 不设（下次继续，不进回归队列） |
| `owe_next` | `QUEUED` | `failed` | `today + 1` |

`MasteryStatus` 加 `IN_PROGRESS = "in_progress"`，`PlanItemStatus` 已有 `IN_PROGRESS`。

**`VerifyLoop` 调整**：`examine` 状态调 `axiom_agent.run()`，Axiom 在该状态内完成多轮追问+引导+判定，**不切 `COACH` 状态**（`COACH` 状态在本变更中废弃不用）。每轮 Axiom 返回 `done=false` 时留在 `EXAMINE`（前端继续传用户回答）；`done=true` 时按 `verdict` 转移：`passed`→`GATE`，`owe_next`→`QUEUE`，`almost`→留在 `EXAMINE`（claim 标 `IN_PROGRESS`，等下次续考，见上「IN_PROGRESS 回归路径」）。

## REST ↔ MCP parity

| REST | MCP | 说明 |
|------|-----|------|
| `POST /v1/examine`（多轮，真实 Axiom） | `gotit_examine` | 多轮端点，返回 `ExamineVerdict{done,...}`，`done=true` 才更新 Claim/PlanItem 状态。支持 `verdict` 直传 bypass（stub/测试） |
| `POST /v1/teach`（多轮，Echo 回讲） | `gotit_teach` | 独立模式，返回 `TeachVerdict{done,...}`，不更新 `Claim`，历史写 `chat_messages`(role=echo/user)。支持 `you_taught_well` 直传 bypass |
| `POST /v1/curate`（Compass 推题） | `gotit_curate` | **只排题**：按 claim text 匹配已入库 claim 加 plan_item 到指定日 |
| `POST /v1/notes/{id}/ingest`（升级） | `gotit_ingest_note` | **抽 claim**：有 LLM key 时用 Compass 抽 claim 带 topic + 加 plan_item；无 key 时 stub fallback |
| `GET/POST /v1/memory` | `gotit_list_memory` / `gotit_add_memory` | 分层记忆读写 |
| `GET /v1/prompts` + `POST /v1/prompts/register` | `gotit_list_prompts` / `gotit_register_prompts` | prompt 版本观测 + 注册 |

现有 `/v1/ingest` / `/v1/today` / `/v1/days` / `/v1/notes` / `/v1/plan/items` 保持。`/v1/examine` 从 stub 升级为真实多轮 Axiom；`/v1/notes/{id}/ingest` 从 stub 升级为 Compass 抽 claim；`/v1/curate` 是新端点只做推题；`/v1/teach` 是新端点做 Echo 回讲。

**职责分离**：`ingest` 抽 claim、`curate` 排题、`examine` 考、`teach` 回讲——四个端点不重叠。

## Postgres impact

采用 **SQL/NoSQL 混合模式**：强查询字段（外键、索引、过滤维度）用关系列，灵活结构（trace、metrics、content、config）用 JSONB 吸收。原则是「按查询场景选型」——harness 需要按 case 跨 run 聚合，所以用两表关系结构；run 级 summary 一次一份，用 JSONB。

新增表（Alembic migration `0002_agent_rewrite`）：
- `prompt_versions` — `agent_name`/`version_label`/`is_active` 关系列 + `config` JSONB（temperature/model 等运行时配置）
- `harness_runs` — run 元信息 + `prompt_versions`/`summary` JSONB（聚合指标）
- `harness_case_results` — 一行一 case，`run_id`/`case_id`/`layer` 关系列 + 索引，`metrics`/`trace` JSONB（支持按 case 跨 run 聚合）
- `memory_entries` — `layer`/`topic`/`user_id` 关系列 + `content`/`source` JSONB

**未建**：原设计的 `examine_runs` 表本变更未实现（per-attempt trace 由 `chat_messages` + harness 承担），后续如需 per-attempt 指标可补。

`claims` 加列：`topic` (varchar(64), nullable, indexed), `tags` (JSONB, default `[]`)。

枚举加值：`MasteryStatus.IN_PROGRESS = "in_progress"`（`almost` 判定用）。

JSONB 字段按需加 GIN 索引（`memory_entries.content`、`harness_case_results.trace`），M0 可不加，后续查询压力上来再补。

Redis：M0 不强依赖（harness 可纯 DB），现有用途不变。

## 目录结构

```
src/gotit/
  core/
    models.py        # 加 ExamineVerdict / TeachVerdict / CompassOutput / MemoryEntry / PromptVersion / HarnessRun / HarnessCaseResult；Claim 加 topic/tags
    loop.py          # COACH 状态废弃不用，examine 内完成引导
    agents/
      __init__.py
      deps.py        # MemoryReader / PromptReader protocols（agent 只读 deps）
      llm.py         # build_model（OpenAI 兼容端点工厂，core 无 api import）
      axiom.py       # Axiom Agent + 多轮 runner
      compass.py     # Compass Agent（抽 claim + 推题）
      echo.py         # Echo Agent（回讲多轮）
  api/
    routes.py        # 加 /v1/teach /v1/curate /v1/memory /v1/prompts*；/v1/examine 升级多轮
    deps.py          # SessionMemoryReader / SessionPromptReader / get_model（编排层 wiring）
  mcp/server.py      # 加 gotit_teach gotit_curate gotit_list_memory gotit_add_memory gotit_list_prompts gotit_register_prompts
  db/
    models.py        # 加 4 张表（JSONB TypeDecorator 跨库）+ Claim 字段
    ops.py           # 加 memory/prompt/harness ops + apply_examine_verdict 三值映射 + list_due_claims 扩展 IN_PROGRESS + curate_claims
  harness/
    __init__.py      # Case / CaseResult / run_harness（runner，写两表）
    cases/dev.py     # dev case 集（prompt/agent/loop/system 四层）
prompts/
  axiom.md compass.md echo.md
scripts/
  run_harness.py     # 跑 dev case 集
  gate.sh            # ruff + mypy + pytest + harness
tests/
  test_day_ops.py test_harness.py test_e2e.py test_loop.py
```

## Risks

- **LLM provider 未定**：直接用 Pydantic AI 的 model 切换（`OpenAIModel`/`AnthropicModel`），M0 默认 OpenAI（pyproject 已有 `openai` 依赖），换 provider 改 settings 注入不改 Agent 代码
- **无 Docker 本地**：测试用 `sqlite+aiosqlite`（`GOTIT_TEST_DATABASE_URL` 未设时），生产路径仍 Postgres
- **harness 成本**：跑 case 调真实 LLM 有 token 成本，dev 集 M0 控制在 5–10 case，gate 默认只跑 dev 不跑 holdout
- **prompt 文件 vs DB 双源**：register 脚本以文件为准写入 DB，运行时只读 DB；git 管 diff，DB 管运行时版本，单一方向不冲突
- **Echo 边界**：M0 Echo 已接真实 LLM（与 Axiom/Compass 同构），无 `LLM_API_KEY` 时走 `you_taught_well` 直传 bypass 用于测试，避免 CI 依赖 LLM
- **`COACH` 状态废弃**：`VerifyLoop.COACH` 在本变更不使用（Axiom 在 `EXAMINE` 内完成引导），保留枚举值不删（避免 migration 改枚举），后续若引入独立 Coach Agent 可复用
- **harness 简化**：原设计拆 case/evaluator/verdict/report/storage 多文件，M0 合并实现为 `harness/__init__.py` + `cases/dev.py`；evaluator/verdict/report 仍 TODO，后续按需拆分
