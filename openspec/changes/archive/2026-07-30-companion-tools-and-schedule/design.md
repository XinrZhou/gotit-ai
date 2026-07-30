# companion-tools-and-schedule — design

## Boundaries

| 块 | 动 | 不动 |
|----|----|------|
| A 工具 | `chat_orchestrator` / `run_chat` 注入**内置**白名单 tools；metadata 记调用 | `verify_finalize` 门语义；用户 MCP connectors 仍可选叠加，但不替代白名单 |
| B 排程 | `apply_examine_verdict` 的 `next_review_at`；`list_due_claims` / `fill_today_from_queue` 排序；再练候选/注入 | Critic、stricter-of-two gate、verdict 三档含义 |
| C UI | DailyBrief / Examine picker 读「原因」字段或只读拼装 | 不新造排程公式 |
| D/E | 文案；docs/harness 记录 | 产品定位、门逻辑 |

## A — Companion 白名单工具

**现状：** `run_chat` 已支持 `tools` / `toolsets`；编排只挂了**用户启用的 MCP connectors**（`entered_toolsets`），没有 gotit 内置 day/examine/memory 工具。计划仍主要靠 prompt 注入的 `today_plan_brief`。

**目标形状：**

```text
用户消息
  → orchestrator 组装 builtin_tools（白名单）[+ 可选 connector toolsets]
  → run_chat(..., tools=builtin, toolsets=connectors?)
  → 模型可能 tool_call → 调 db.ops（同 REST/MCP）
  → 回复落库；metadata.tool_calls[] = { name, args_digest, ok, summary }
```

**白名单（少而准，首版）：**

| 工具名（示意） | 背后 ops | 用户可感知 |
|----------------|----------|------------|
| `get_today` | `get_today` / plan + due | 今天计划与欠账 |
| `list_due_claims` | `list_due_claims` | 欠哪些 |
| `start_examine` | 已有 examine 入口（claim_id / note_id）或返回「可开考」深链载荷 | 帮开考 / 推进 |
| `get_failure_lessons` | failure digest / memory 只读（budget） | 带着上次教训 |
| `add_memory`（可选） | `memory` 写入短条 | 记下该记的 |

实现注意：

- 工具实现放 **api 薄封装 → db.ops**（或 core 纯函数 + ops）；**不要**在 `gotit.core` 里 import FastAPI/MCP。  
- `start_examine` 优先复用现有 examine API/会话启动，避免第二套考题引擎。  
- Stub（无 `LLM_API_KEY`）路径可不跑真实 tool loop；测着用 mock tools。  
- REST 聊天与 MCP `gotit_post_message` 共用 orchestrator → 自动同构。

## B — 可解释排程 + 易混进再练

**现状：**

- `owe_next` → `next_review_at = today + (1 + 2×prior_failures)`；`passed` 清空；`almost` 不改期、留在今日。  
- `list_due_claims`：状态 ∈ queued/not_yet/in_progress 且 `next_review_at` 空或 ≤ as_of。  
- `fill_today_from_queue`：按 fail_counts 降序。  
- Mastery graph：`confused_with` + failure lesson budget 注入 Axiom。

**演进（确定性，允许简化 FSRS 思想）：**

1. **公式进 core**（如 `gotit.core.schedule`）：输入 verdict、prior_failures、可选简易稳定性字段；输出 `next_review_at` + `reason_code`。  
   - 首版可不引入完整 FSRS 四参数；可保留分段间隔表，但 **文档写出公式**，单测钉死。  
   - `almost`：建议明确「仍 due 今日或 +0/+1 天」写进 design 实现注释，避免各 Agent 各写各的。  
2. **`apply_examine_verdict`** 只调用该纯函数写回（门仍先跑完再写回）。  
3. **Due 排序键**（示意）：`(overdue_days desc, severity, confuse_weight, id)`；`confuse_weight` 来自 `confused_with` 边权（只读 graph ops）。  
4. **再练线索：** 在现有 failure lesson 注入旁，增加「最高权易混邻居 claim 短摘」；条数/字符预算沿用 `FAILURE_LESSON_*` 量级。  
5. **禁止：** 模型生成 `next_review_at` 覆盖代码结果。

**可选持久化：** 若公式需要 `stability`/`reps`，用 claim 上可空列或 JSON metadata + alembic；没有必要勿加列。

## C — 「为何今天欠」

**数据：** 扩展 `Claim` / today 视图最小字段，例如：

```text
due_reason_code: overdue | almost_today | owe_scheduled | confuse_boost | queued
due_reason_text: 短中文（服务端拼，前端不解析公式）
```

或首版前端用已有 `next_review_at` + status + confuse API **只读拼装**（改动更小）。优先 **服务端给 reason**，避免三处 UI 各写一套。

**表面：** `DailyBrief`、空线程、Examine picker；一键开考不变。

## D / E（同波可选）

- D：文案 only（PRODUCT 温度）。  
- E：`docs/` 或本夹 `notes-gold.md` + harness/脚本；固定 5～10 claim 对照表模板。

## REST / MCP / Postgres

| 面 | 影响 |
|----|------|
| REST | `GET /v1/today` due 项可能多 reason；chat 消息 metadata 多 `tool_calls` |
| MCP | 聊天工具链走同一 orchestrator；若新增独立 tool，镜像 db.ops |
| DB | 排程若需新列才 migration；工具轨迹进 message.metadata 即可 |

## 风险

| 风险 | 缓解 |
|------|------|
| 模型乱调工具 / 刷写 | 白名单 + 写操作少；`add_memory` 限长 |
| PromptedOutput 与 tool 不兼容 | 实测；不行则 tool 轮与最终 ChatTurn 分步（design 实现时记一笔） |
| 排程变严导致欠账爆炸 | 公式有上限间隔；UI 只展示前 N 条 |
| 并行 Agent 改同一文件 | A↔B 默认文件面分离；`SYSTEM.md` / `Claim` 模型合并时后到者捏合 |
