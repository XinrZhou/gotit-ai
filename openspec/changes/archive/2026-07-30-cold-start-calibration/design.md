# cold-start-calibration — design

## Boundaries

| 块 | 动 | 不动 |
|----|----|------|
| A 核心 | 纯函数选题 / θ 更新 / 早停 | FastAPI/MCP；LLM 定档 |
| B 持久化 | claim 校准字段；session + trace 表 | 删除用户学习数据 |
| C 写回 | 复用 `apply_examine_verdict` + `record_fail_event`；**校准路径专用** confuse 种子 | 日常 `grow_confused_edges_for_fail` 语义 |
| D API | REST + MCP → `db.ops.calibration` | 第二套领域逻辑 |
| E obs | session.trace；synthetic 端点 / harness | 对外刷榜 UI |
| F Web | 空态 CTA + 极简校准页 | 完整 Examine 壳改造 |

## A — 确定性 CAT（`gotit.core.calibration`）

框架无关；单测钉死公式。

### 题目标注（每道校准题 = 一个 Claim + 元数据）

| 字段 | 含义 | 缺省 |
|------|------|------|
| `difficulty` | 1–5 整数难度档 | `3` |
| `discrimination` | 区分度 > 0 | `1.0` |
| `knowledge_key` | 知识点轮换键 | `topic`；空则 `"_untagged"` |

### 能力 θ

- 连续标量，与难度同尺度（中心 ≈ 3）。
- 先验：`theta0 = 3.0`，`se0` 较大（如 `1.5`）。
- 答对 / 答错后用简化 2PL 信息更新（确定性）：正确升高 θ、错误降低；更新幅度与 `discrimination` 和当前 `|θ−d|` 相关。  
  实现时把更新式写进模块 docstring，禁止「模型估个分数」。

### 选题（每步）

候选 = 会话范围内未测 claim。

打分（高者优先）：

1. **信息量**：在当前 θ 下，难度接近 θ 且区分度高的题优先（简化 Fisher：`a² · p · (1−p)`，`p` 为 2PL 正确概率）。
2. **知识点轮换**：刚测过的 `knowledge_key` 降权 / 冷却（避免连测同一点）。
3. **易混推断**：若某点已测且存在（或将种子的）邻点，邻点信息量降权，少测一点。

禁止纯随机、纯顺序。

### 难度自适应

从中档起；答对后偏好更难，答错后偏好更易——由 θ 移动自然实现，不另开启发式分支也可，但测试需覆盖「连对升难 / 连错降难」。

### 早停 + 上限

| 条件 | 行为 |
|------|------|
| `se(θ) ≤ SE_STOP`（如 `0.45`）且至少 `MIN_ITEMS`（如 `4`） | 停，`stop_reason=converged` |
| 连续 `STABLE_N` 步 θ 变化 < ε | 停，`stop_reason=stable` |
| 题数 ≥ `MAX_ITEMS`（**10**，可配 8–12） | 停，`stop_reason=max_items` |
| 候选耗尽 | 停，`stop_reason=exhausted` |

常量集中在 `core/calibration.py`，可测可调；调参属小迭代。

## B — 数据模型

### Claim 校准元数据

优先 **JSONB 旁字段** 或列：

- `ClaimRow.calibration` JSON：`{difficulty, discrimination, knowledge_key}`  
  或三列 `difficulty` / `discrimination` / `knowledge_key`。

缺省由 ops 在读时填充，不强制迁移旧行非空。ingest / stub_extract 可写默认。

### CalibrationSession

| 字段 | 说明 |
|------|------|
| id, user_id | |
| status | `active` \| `completed` \| `cancelled` |
| scope | 可选 `note_id` / `topic` / `claim_ids`（池子） |
| theta, se | 当前估计 |
| stop_reason | 结束后填写 |
| item_count | |
| trace | JSON 数组（见下） |
| summary | 结束后初始化摘要（due 数、fail 数、边数） |
| created_at / completed_at | |

### Trace step 形状

```text
{
  "n": 1,
  "claim_id": "...",
  "difficulty": 3,
  "discrimination": 1.2,
  "knowledge_key": "redis",
  "theta_before": 3.0,
  "se_before": 1.5,
  "info": 0.42,
  "select_reason": "max_info+rotate",
  "outcome": "correct" | "incorrect",
  "theta_after": 3.4,
  "se_after": 1.1,
  "stop": false
}
```

alembic：`0010_cold_start_calibration.py`（claims 元数据 + calibration_sessions）。

## C — 写回闭环

校准**不**跑 Critic。每题学习者给出对/错（或 UI 二元），ops 映射：

| outcome | 写回 |
|---------|------|
| `correct` | `apply_examine_verdict(..., verdict="passed")` |
| `incorrect` | `apply_examine_verdict(..., verdict="owe_next", prior_failures=0)` + `record_fail_event(..., reason="calibration")` |

### 校准专用 confuse 种子（仅 finalize / 答错路径）

当 claim A 答错：

1. 同 `knowledge_key` / `topic` 下、会话池内尚未测的邻点 B（上限 N，如 2）：`increment_confused_with(A, B)`（weight+1，无则建边）。
2. **不**要求 B 已有 fail_event（这是与日常 `grow_confused_edges_for_fail` 的差异）。
3. 日常 verify **不改**；仅 `db.ops.calibration` 调用种子函数（可放 `graph.py` 新函数 `seed_confused_for_calibration`，避免误用）。

### 答对邻点

不自动 `passed` 邻点（避免假懂传染）。仅降权选题。

### 会话结束 → 今日欠账

`finalize_calibration`：

1. 对所有答错 claim：已由逐步写回排进 due（`owe_next` 间隔 ≥1d 时：若希望**当天**看见欠账，校准答错可写 `next_review_at = as_of` 或额外 `almost`——**钉死：答错 → `almost` 留今日 due，并仍记 fail_event**；再次正式考再走 `owe_next` 间隔。  
   **更贴产品的钉死方案（采用）：**  
   - 答错 → verdict **`almost`**（`next_review_at = as_of`，当日 due）+ `fail_event` + confuse 种子。  
   - 答对 → **`passed`**。  
   这样「校准完当天就有欠账」与 `schedule.py` 语义一致，无需旁路改公式。
2. `fill_today_from_queue(as_of)` 可选调用，把 due 填进今日计划。
3. `summary` 写入：测了几题、停因、passed/failed 数、confused 边数、due 快照条数。

## D — REST / MCP

| 面 | 端点（示意） |
|----|----------------|
| REST | `POST /v1/calibration/start` `{note_id? topic? claim_ids?}` → session + first item |
| | `POST /v1/calibration/{id}/answer` `{claim_id, outcome}` → next item \| done |
| | `GET /v1/calibration/{id}` → session + trace |
| | `POST /v1/calibration/synthetic` `{true_theta, pool, strategy?}` → 跑完 + 误差指标 |
| MCP | `gotit_calibration_start` / `answer` / `get` / `synthetic` → 同 ops |

Stub（无 LLM）：校准不依赖 LLM，可全链路测。

## E — Synthetic

- 输入：已知 `true_theta`、候选池（带难度/区分度）、答题策略（如 2PL 伯努利或「θ≥d 则对」确定性策略）。
- 输出：最终 `theta_hat`、`|hat−true|`、题数、stop_reason、trace。
- harness case + pytest 钉：中档用户估计误差在带宽内；高/低用户方向正确。

## F — Web（最小）

- `EmptyState` / 笔记 ingest 成功后 / DailyBrief 无 due 且有未校准池：安静 CTA「先摸底一下」。
- 页或 modal：展示当前 claim 文本、进度 `n/MAX`、对 / 错两按钮、结束摘要（停因 + 今日欠几条）。
- 遵循 `ui-apple.mdc`；不鸡血。
- 结束 CTA：「去看今天欠的」→ 现有 DailyBrief / 开考。

## 风险

| 风险 | 缓解 |
|------|------|
| 池子太小（< MIN_ITEMS） | start 时校验；不足则仍可跑完 exhausted，summary 说明 |
| 答错全标 almost 导致当日 due 暴涨 | 单次校准池建议按 note/topic 限制；UI 只展示前 N；MAX_ITEMS=10 |
| 元数据全默认导致选题退化 | 单测覆盖「高区分度优先」；文档要求重要材料可标 discrimination |
| 与正式 examine 混淆 | UI 文案「摸底」；fail reason=`calibration`；不写 Critic trajectory 强制路径 |

## 文件落点（实现指引）

```text
src/gotit/core/calibration.py          # 纯函数
src/gotit/core/models.py               # Calibration* views
src/gotit/db/models.py                 # ORM + alembic 0010
src/gotit/db/ops/calibration.py        # start/answer/finalize/synthetic
src/gotit/db/ops/graph.py              # seed_confused_for_calibration
src/gotit/api/routes/calibration.py    # router
src/gotit/mcp/server.py                # thin tools
web/src/pages/... 或 components        # 最小校准 UI
tests/test_calibration*.py
```
