# Agent rewrite — personal exam-prep assistant

> **Status: implemented 2026-07-28** (not yet archived — pending commit). Gate
> green: ruff + mypy + 7 pytest + harness dev set 4/4.
>
> **Delivery notes (deviations from original design, kept for honesty):**
> - Echo endpoint shipped as `POST /v1/teach` + MCP `gotit_teach` (not `/v1/echo`).
> - `examine_runs` table was **not** built as a separate table; per-attempt
>   trace is carried by `chat_messages` + the harness two-table model. This can
>   be added later if per-attempt analytics are needed.
> - Echo is wired to the real LLM like Axiom/Compass (not a stub); a `you_taught_well`
>   bypass field exists for stub/tests when no LLM key is configured.
> - Harness was simplified to `src/gotit/harness/__init__.py` (runner) +
>   `cases/dev.py` (case set) instead of the planned case/evaluator/verdict/
>   report/storage split. Evaluator/verdict/report remain TODO.
> - Prompt registration is `POST /v1/prompts/register` + `gotit_register_prompts`
>   (no separate `scripts/register_prompt.py`).
> - Frontend M0 shipped examine multi-turn + Echo modal only; the `[今日][历史][资讯]`
>   tabs, topic-grouped queue, and A/C/E avatars are deferred.
> - LLM settings are `llm_base_url` / `llm_api_key` / `llm_model` (not
>   `gotit_llm_provider` / `gotit_openai_api_key`).

## Why

gotit-ai 当前是 stub 检验台（examine/ingest 都是桩，靠调用方传 `passed` 回写）。本变更把它重构成一个**个人备考助手**：多 Agent 协作检验你是否真会，面向社招备考场景（项目 / 算法 / AI / 八股 / 行为面），流程人性化、前台不企业级死板，但后台用工程化 harness 保证 prompt/agent 可迭代、可观测、可验证。

采用三层分离架构（LLM / Agent / Platform），Agent 之间通过持久身份、共享记忆与接力编排协作。Agent 框架选用 Pydantic AI（同源 Pydantic 生态、轻、多 provider、structured output 原生、agent-as-tool + 共享 deps 实现多 Agent 协作）。

## Scope

### In

- **3 个 Agent**（职能分工，非按考试领域）：
  - **Axiom**（考官）— 多轮追问+引导+判定，在 `EXAMINE` 状态内完成（不切 `COACH`），`/v1/examine` 为多轮端点（`done` 区分中间轮/最终轮）
  - **Compass**（管家）— 整理材料成 claim（走 `/v1/notes/{id}/ingest`）、排复习、每日推题（`/v1/curate` 只推题，遗忘曲线 + 弱点加权）
  - **Echo**（回讲官）— 你给它讲课，它扮不懂的学生提问；独立多轮模式（`/v1/teach`），不走 `VerifyLoop`，复用 `chat_messages`（role=echo/user）
- **Sage（复盘官）整个后置**：M0 只存 `memory`/harness 数据，Sage 后续读这些出报告，M0 不建骨架
- **Pydantic AI 接入**：`core/agents/`（3 Agent + deps），3 个 Agent 均接真实 LLM（无 `LLM_API_KEY` 时各端点走 stub bypass 用于测试）。直接用 Pydantic AI 的 model 切换 provider，不另包 `LlmClient` 协议
- **memory 职责分离**：agent 通过 deps 只读 memory（注入 prompt），所有 DB 写由 `db.ops` 编排层做，`core/agents` 无副作用
- **IN_PROGRESS 回归**：`almost` 判定的 claim 标 `IN_PROGRESS`，`list_due_claims` 扩展查 `IN_PROGRESS`，Compass 推题时 due > IN_PROGRESS > mastered
- **人性化流程**：对话式判定（追问不立刻判、答错自然引导、最后才说"过了/还差点/欠着下次"），连续谱 `passed`/`almost`/`owe_next` 而非 passed/failed 二元
- **判定映射**：`passed` → `MASTERED`，`owe_next` → `QUEUED`+`next_review_at`，`almost` → `IN_PROGRESS`（新中间态，不进队列也不算掌握，下次续考）；`PlanItem` 对应 `verified`/`failed`/`in_progress`
- **分层记忆系统**：长期（弱点/偏好）+ 工作（当前对话）+ 跨会话（今天考的明天还记得），3 Agent 共享读
- **提示词管理**：`prompts/*.md` 文件 + git 管版本 + `prompt_versions` 表 + register 脚本
- **企业级系统 harness**：四层（prompt/agent/loop/system）+ runner/evaluator/verdict/report + `harness_runs`/`harness_case_results` 两表（关系表支持按 case 跨 run 聚合）+ gate 集成
- **观测**：`examine_runs` 表留痕（prompt_version / verdict / score / evidence / tokens / latency / trace 多轮）
- **数据**：`Claim` 加 `topic`/`tags`（知识图谱后置留位），`MasteryStatus` 加 `IN_PROGRESS`，`chat_messages` role 扩展 `echo`
- **前端**：Apple 黑白；M0 交付 examine 多轮 + Echo 回讲 modal；`[今日][历史][资讯]` tab、队列按 topic 分组、A/C/E 单字 SVG 头像后置
- **REST/MCP 对等**：新端点与 MCP 工具共享 `core/agents` + `db.ops`；职责分离（ingest 抽 claim / curate 排题 / examine 考 / teach 回讲）
- **测试 + gate**：单测 + 端到端测试 + harness dev case 集进 gate

### Out

- 知识图谱依赖链与可视化（`Claim` 只加 `topic`/`tags` 留位）
- OpenClaw 资讯接入 / 备忘录更新（gotit 暴露 MCP，频道在 OpenClaw，后置）
- Sage 复盘官（整个后置：M0 只存数据，Sage 骨架与报告生成后续做）
- 模拟面试（Mirror）/ 语音对答 / 面经库（后置）
- 间隔重复调度算法（M0 用简单遗忘曲线加权，SM-2 后置）
- 多用户 / OAuth

## Non-goals

- 不做企业级 Skill 管理平台：harness 是个人项目维护工具，不做 LLM-as-Judge / Jury Debate / TextGrad / Pareto 自动 adopt，人就是 judge
- 不做频道适配器（Feishu/Telegram 在 OpenClaw）
- 不取代用户判断"学什么"（Compass 推题是建议，不是强制）

## Verification

- `./scripts/gate.sh` 通过（ruff + mypy + pytest + harness dev set）
- Axiom 端到端：贴一段 AI 材料 → Compass 抽 claim → Axiom 多轮考 → 最终轮 `ExamineVerdict{done:true, verdict, score, evidence, follow_up}`，`Claim` 状态按映射更新（passed→MASTERED / almost→IN_PROGRESS / owe_next→QUEUED）。无 LLM key 时用 `verdict` 直传 bypass 验证映射（`tests/test_e2e.py`）
- Echo 回讲端到端：进入回讲模式 → Echo 多轮提问 → 最终轮 `TeachVerdict{done:true, you_taught_well, gaps}`，历史写 `chat_messages`(role=echo/user)
- harness dev 集 4 case 跑通（prompt/agent/loop/system 四层），生成 baseline run 存入 `harness_runs` + `harness_case_results`，verdict=pass
- 改一版 Axiom prompt → `POST /v1/prompts/register` → 跑 harness → 按 case 跨 run 对比通过率/score（`list_harness_case_results` 支持按 case_id 聚合）
