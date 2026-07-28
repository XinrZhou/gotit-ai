# Tasks — agent-rewrite

按顺序执行，每步可独立跑 gate。`[gate]` 标记的步骤需通过 `./scripts/gate.sh`。
全部步骤已完成（2026-07-28），gate 全绿。

## 1. 地基：依赖与目录

- [x] `pyproject.toml` 加 `pydantic-ai>=0.30`，`uv sync --all-extras`（实际装到 2.18.0）
- [x] 建 `prompts/`、`src/gotit/core/agents/`、`src/gotit/harness/cases/` 目录骨架
- [x] `src/gotit/core/agents/__init__.py` 空包
- [x] [gate] `uv run ruff check . && uv run mypy src`

## 2. 数据模型与 migration

- [x] `core/models.py` 加 `ExamineVerdict`、`TeachVerdict`、`CompassOutput`/`ExtractedClaim`/`Recommendation`、`MemoryEntry`、`PromptVersion`、`HarnessRun`、`HarnessCaseResult`
- [x] `core/models.py` `Claim` 加 `topic`/`tags`（`MasteryStatus.IN_PROGRESS` 已存在，无需加）
- [x] `db/models.py` 加跨库 `JSONB` TypeDecorator + `MemoryEntryRow`/`PromptVersionRow`/`HarnessRunRow`/`HarnessCaseResultRow`（4 张表，未建独立 `examine_runs`）
- [x] `db/models.py` `ClaimRow` 加 `topic`/`tags` 列
- [x] Alembic migration `0002_agent_rewrite`（干净库 upgrade/downgrade 双向通过）
- [x] [gate] `uv run pytest tests/test_day_ops.py`（回归现有）

## 3. LLM 接入（直接用 Pydantic AI，不包 LlmClient）

- [x] `api/settings.py` 已有 `llm_base_url`/`llm_api_key`/`llm_model`（无需新增 provider 配置）
- [x] `core/agents/llm.py`：`build_model(base_url, api_key, model_name)` 纯工厂（core 无 api import）
- [x] `api/deps.py`：`get_model()` lru_cache 读 settings 构造共享 model
- [x] [gate] `uv run mypy src`

## 4. 提示词管理

- [x] 写 `prompts/axiom.md`（人格 + 出题策略 + 判定标准 + 输出契约）
- [x] 写 `prompts/compass.md`、`prompts/echo.md`
- [x] `src/gotit/prompts/__init__.py`：`load_prompt_file`/`load_prompt_dir`（frontmatter + body + content_hash + 稳定 uuid5）
- [x] `db/ops.py` 加 `register_prompts`（upsert + 每 agent 最新设 active）/ `get_active_prompt` / `list_prompts`
- [x] 注册入口：`POST /v1/prompts/register` + `gotit_register_prompts`（未单独建 `scripts/register_prompt.py`）
- [x] [gate] `uv run pytest`

## 5. 记忆系统

- [x] `db/ops.py` 加 `add_memory` / `list_memory`（分层 + topic 过滤）
- [x] `core/agents/deps.py`：`MemoryReader` / `PromptReader` protocols（agent 只读 deps，不写 DB）
- [x] `api/deps.py`：`SessionMemoryReader` / `SessionPromptReader` 实现
- [x] [gate] `uv run pytest`（记忆读写由 `test_e2e.py` 覆盖）

## 6. Axiom Agent + 判定映射 + 多轮

- [x] `core/agents/axiom.py`：`build_axiom_agent` + `run_axiom`，输出 `ExamineVerdict{done,...}`，memory 只读注入
- [x] `db/ops.py` 加 `apply_examine_verdict`（三值映射：passed→MASTERED+清 review / almost→IN_PROGRESS / owe_next→QUEUED+today+1；PlanItem 同步）
- [x] `db/ops.py` `list_due_claims` 扩展含 `IN_PROGRESS`
- [x] `api/routes.py` `/v1/examine` 升级多轮（claim_id + answer + history → ExamineVerdict，done=true 时 writeback）；支持 `verdict` 直传 bypass
- [x] `mcp/server.py` `gotit_examine` 同步升级
- [x] [gate] `uv run pytest`（三值映射 + 多轮由 `test_day_ops`/`test_e2e` 覆盖）

## 7. Compass Agent（抽 claim + 推题）

- [x] `core/agents/compass.py`：`build_compass_agent` + `run_compass`，输出 `CompassOutput{claims, recommendations}`
- [x] `db/ops.py` `ingest_note` 重构接收 `claims` 参数（None 时 stub fallback）；`curate_claims`（按 text 匹配 claim 加 plan_item）
- [x] `api/routes.py` `/v1/notes/{id}/ingest` 升级（有 LLM key 用 Compass，否则 stub）；加 `POST /v1/curate`
- [x] `mcp/server.py` `gotit_ingest_note` 升级 + 加 `gotit_curate`
- [x] [gate] `uv run pytest`

## 8. Echo 回讲（独立多轮模式）

- [x] `core/agents/echo.py`：`build_echo_agent` + `run_echo`，输出 `TeachVerdict{done,...}`（接真实 LLM，与原设计 stub 不同）
- [x] `api/routes.py` 加 `POST /v1/teach`（多轮，topic + answer + history → TeachVerdict，不更新 Claim）；支持 `you_taught_well` 直传 bypass
- [x] `mcp/server.py` 加 `gotit_teach`
- [x] [gate] `uv run pytest`

## 9. 记忆 + prompt 观测接口

- [x] `api/routes.py` 加 `GET/POST /v1/memory`、`GET /v1/prompts`、`POST /v1/prompts/register`
- [x] `mcp/server.py` 加 `gotit_list_memory` / `gotit_add_memory` / `gotit_list_prompts` / `gotit_register_prompts`
- [x] [gate] `uv run pytest`

## 10. 系统级 harness 骨架（两表）

- [x] `src/gotit/harness/__init__.py`：`Case`/`CaseResult`/`run_harness`（runner，写 `harness_runs` + `harness_case_results` 两表）
- [x] `db/ops.py` 加 `add_harness_run` / `add_harness_case_result` / `finalize_harness_run` / `list_harness_runs` / `list_harness_case_results`
- [x] `tests/test_harness.py`：两表写入 + 跨 case 聚合验证
- [x] [gate] `uv run pytest tests/test_harness.py`
- [ ] evaluator / verdict / report 模块（TODO，M0 未拆，合并实现）

## 11. dev case 集 + baseline run

- [x] `src/gotit/harness/cases/dev.py`：4 个 case 覆盖 prompt/agent/loop/system 四层（不依赖 LLM）
- [x] `scripts/run_harness.py --label baseline`，baseline run 4/4 pass 存入 DB
- [x] [gate] `uv run python scripts/run_harness.py --label gate`（dev 集跑通即过）

## 12. gate 集成

- [x] `scripts/gate.sh` 加 `uv run mypy src` + `uv run python scripts/run_harness.py --label gate`
- [x] [gate] `./scripts/gate.sh` 全绿

## 13. 前端改造

- [x] `web/src/App.tsx` `/v1/examine` 接真实 Axiom 多轮（history + answer → follow_up/verdict，无 LLM 时 stub 兜底）
- [x] 加「回讲」入口（Echo 独立模式 modal，多轮）
- [x] [gate] `cd web && npm run build`
- [ ] 顶部 `[今日][历史][资讯]` tab、队列按 topic 分组、A/C/E 单字 SVG 头像（TODO，M0 未做）

## 14. skills/AGENTS 同步

- [x] `skills/gotit/SKILL.md` 更新新 MCP 工具列表（teach/curate/memory/prompts）
- [x] `AGENTS.md` Commands 加 harness run
- [x] [gate] `./scripts/gate.sh`

## 15. 收尾

- [x] 端到端测试 `tests/test_e2e.py`：register prompts → note+ingest → examine verdict → curate → teach → memory → prompts 观测
- [x] 检查 OpenSpec 三文件与代码一致（已同步实现偏差）
- [x] [gate] `./scripts/gate.sh` 全绿（ruff + mypy + 7 pytest + harness 4/4）
