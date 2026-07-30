# companion-tools-and-schedule — tasks

> 编号对齐 `docs/agent-prompts/下一批功能.md`（任务 1–5）。  
> **A / B / E 可并行**；**C 依赖 B 的 reason 字段或约定**；**D 随时可做**。

## Spec（任务 0）

- [x] proposal / design / tasks
- [x] `openspec/changes/README.md` 登记本夹
- [x] 实现过程中保持本 tasks 勾选；整波完成后归档并更新 `docs/SYSTEM.md`

---

## A — Companion 真调工具（任务 1）

### Backend

- [x] 定义白名单 builtin tools（get_today / list_due / start_examine / get_failure_lessons；可选 add_memory）→ 调 `db.ops`
- [x] `chat_orchestrator.post_message_chain`：注入 builtin `tools`（保留可选 connector `toolsets`）
- [x] 工具调用摘要写入 agent 消息 `metadata.tool_calls`（可解释、可回放）
- [x] 无 LLM key 的 stub 路径行为明确（不假造成功写库）

### MCP

- [x] 确认 `gotit_post_message` 走同一 orchestrator（自动对齐）；若有独立新 ops tool，补 MCP 镜像

### Tests

- [x] mock tools：编排或 runtime 在给定用户意图下会发起调用（或单元测 tool 函数本身 + metadata 形状）
- [x] 相关 pytest 通过；可选 `./scripts/gate.sh`

### Docs

- [x] `docs/SYSTEM.md`：Shipped 写入 companion builtin tools；Not done 收窄「agent-as-tool」表述
- [x] 对外说法若变：`README.md` + `README.zh-CN.md`

---

## B — 间隔复习排程 + 易混进再练（任务 2）

### Backend / core

- [x] `gotit.core` 纯函数：verdict → `next_review_at` + `reason_code`（公式写进 docstring；禁止 LLM 定日期）
- [x] `apply_examine_verdict` 改用该函数；`almost` / `passed` / `owe_next` 行为单测钉死
- [x] `list_due_claims` / `fill_today_from_queue`：排序纳入到期紧迫度 + 严重度 + 可选 confuse 权重
- [x] 再练/examine 注入：budget 内附带易混邻居短摘（衔接 mastery graph）
- [x] 若需新列：alembic + ORM；否则不加

### MCP / REST

- [x] `GET /v1/today`（及 MCP 等价）due 列表顺序与新排序一致；若暴露 reason，REST↔MCP 同构

### Tests

- [x] 不同 verdict / prior_failures → 日期符合公式
- [x] 存在 `confused_with` 边时，排序或再练候选含预期邻居
- [x] 相关 pytest；可选 gate

### Docs

- [x] `docs/SYSTEM.md`：写清排程规则摘要（替换「简单 interval」表述）
- [x] 对外若提「间隔复习」：README 双语点到为止

---

## C — 「为何今天欠」UI（任务 3）

### Backend（若 B 未给 reason）

- [x] 最小 `due_reason_code` + `due_reason_text`（B 已在 `/v1/today` due 项暴露）

### Web

- [x] `DailyBrief` / 空线程 / Examine picker：欠账一行人话原因（到期 / 还差点 / 易混等）
- [x] 一键开考不回归；遵循 `ui-apple.mdc`（安静、不鸡血）

### Docs

- [x] SYSTEM 一句：今日焦点展示欠账原因

---

## D — 温度文案扫尾（任务 4，可选）

- [x] Chat / DailyBrief / Verify chip 旁 / Examine·Teach·Drill 空态：去鸡血与官方腔
- [x] 只改文案与轻微字色；列出前后对照
- [x] 不改 API / 门逻辑

---

## E — 小样本质量对照（任务 5，可选）

- [x] `notes-gold.md`（本夹或 `docs/`）：5～10 claim 选取规则 + 对照表模板
- [x] 最小可跑方式（复用 harness/pytest 或 `uv run` 脚本说明）
- [x] 记录字段：日期 / claim / examine / critic / gate / 备注

---

## Gate（整波收口）

- [x] `./scripts/gate.sh` 或至少 ruff + 相关 pytest + web build
- [x] 归档本夹 → `openspec/changes/archive/2026-07-30-companion-tools-and-schedule/`
- [x] `openspec/changes/README.md` 更新 active 列表
