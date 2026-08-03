# Design: daily-brief-semantic-cleanup

## Problem (precise)

| 混入源 | 数据 | 是否「今天欠」 |
|--------|------|----------------|
| Due claim | `/v1/today`.due_claims（含 `due_reason_*` / `failure_hint`） | **是** — 排程/状态裁定 |
| Plan-open claim | 今日 `plan_items`：`status != verified` 且有 `claim_id`，且 id ∉ due 集合 | **是（弱）** — 今日计划未核销；应可开练，须诚实标注来源 |
| Note claim | 任意 `notes` 含 `claim_ids` | **否** — 仅「库里有料可考」 |

当前 `DailyBrief` 三者同列、同标题「今天还欠这些」；`ChatPage.hasDailyBrief` 在仅有 note claim 时也为 true → **语义失真**。

## In Scope

1. 重新定义 Brief 行集合与首页是否展示 Brief。
2. 标题 / 副文 / 行 meta 与「欠」对齐；无欠时的空闲文案（账清 vs 无料）。
3. 笔记「还可练」若保留，必须**降级**：非「欠」标题下、非默认主列表，或完全移出 Brief（见 UI behavior）。
4. 手测 + `npm run build`；SYSTEM 短同步。

## Out Scope

见 `proposal.md` Out。额外强调：

- 不改 due 计算、`explain_due_reason`、failure_hint 生成
- 不新增推荐 / LLM 排序
- 不在本夹做考完回程 CTA、顶栏入口收敛

## Data source（只读现有）

全部来自已有 workspace snapshot（`useWorkspace` ← `GET /v1/today` 等），**不新开 endpoint**：

| 用途 | 字段 |
|------|------|
| 真欠练 | `dueClaims[]` — `id`, `text`, `due_reason_text`, `failure_hint`, `preferred_check_mode`, … |
| 今日计划未核销 | `items[]`（plan）— `claim_id`, `title`, `status`, `topic`, `project_id` |
| 笔记可考（旁路） | `notes[]` — `claim_ids`, `title`/`excerpt` |
| 日关闭 | `dayClosed`, `closeSummary` |
| Bootcamp | `bootcamp.show`（Brief 仍被 bootcamp 抢主舞台时不展示 Brief） |

**真欠行（Owed row）定义（本夹契约）：**

```text
owed =
  dueClaims
  ∪ plan items where
       status ≠ "verified"
       ∧ claim_id ≠ null
       ∧ claim_id ∉ dueClaims.ids
```

**非欠（Available / library）：** 仅来自 notes 的「按笔记开考」入口 — **不得**计入 owed，**不得**单独把 `hasDailyBrief` 置 true。

## UI behavior

### A. 何时展示 DailyBrief（首页 / 空线程）

`hasDailyBrief`（或重命名后的等价布尔）SHALL 为：

```text
!dayClosed ∧ !bootcamp.show ∧ owed.length > 0
```

不再因「有笔记带 claim」而为 true。

### B. Brief 列表内容

1. **默认列表（主）：** 仅 owed 行（先 due，再 plan-open；保持现有去重 / `maxItems`）。
2. **每行：**
   - due：展示 `due_reason_text`（或既有 `dueReasonLine`）；可挂 `failure_hint`
   - plan-open 且无 due reason：静默一行来源，例如「今日计划」——**禁止**伪装成 overdue/排程理由
3. **标题：** 有 owed 时保持人话「今天还欠这些」（或等价「欠」语义）；副文可保留「挑一条开考，过关才算会」。
4. **笔记可考：**
   - **推荐（默认实现）：** 移出 Brief；用户从「考我」选题页 / 资料库 / 「全部」进 Examine 仍可开考（现有 Examine picker 已含 notes — 本夹不改 picker 亦可）。
   - **若保留次要区：** 必须在 Brief **下方**独立安静区块，标题不得含「欠」（如「库里还可练」），且不计入 head 欠账计数。

### C. 无 owed 时的空态（替换假 Brief）

| 条件 | 表现 |
|------|------|
| 无 owed，库空/几乎无 claim 可考 | 维持现有「今天暂时没事」+ 主 CTA「添加资料」（S1） |
| 无 owed，但库里仍有 claim/笔记可考 | **账清态**：人话如「今天账清了」；主 CTA 仍偏「添加资料」或安静「继续练」→ 打开 examine picker；**禁止**「今天还欠这些」 |
| dayClosed | 不变：收工文案 |

不在本夹引入新推荐列表。

### D. 「全部 N」按钮

计数与「查看全部」SHALL 只反映 owed（或 owed + 明确标注的次要区分别计数）。不得把 note 行算进「欠」的总数。

### E. 不变

- 行点击仍走既有 `onExamineClaim` / `claimVerifyCta`（form-follows-claim）
- 不改 gate / schedule / `/v1/today` 载荷形状（除非只读字段展示）
- Apple UI tokens；无新响亮选中态

## Acceptance Criteria

### AC1 — 欠字可信

**Given** 用户有若干带 `claim_ids` 的笔记，且 `due_claims` 为空、今日无未核销 plan claim  
**When** 打开 App 空首页（非 bootcamp、未收工）  
**Then** 不出现标题含「欠」的 DailyBrief；不把笔记行列为「今天还欠」

### AC2 — 真欠仍一键可开

**Given** `due_claims` 非空（或仅有合格 plan-open）  
**When** 打开空首页  
**Then** 展示 DailyBrief；列表每一行均属于 owed；due 行可见 why（reason 或既有 fallback）；点击仍进入对应开考/回讲

### AC3 — 计划未核销诚实

**Given** 某 plan item 有 `claim_id`、未 verified、不在 due 集合  
**When** 出现在 Brief  
**Then** 可点开练；meta 不谎称排程 overdue；若无 `due_reason_text` 则显示计划来源类文案

### AC4 — 计数不掺水

**Given** Brief 可见且存在 note 可考（若 UI 仍露出次要区）  
**When** 查看标题旁计数 /「全部 N」  
**Then** N 只统计 owed（次要区若存在则单独计数或不计入欠账 N）

### AC5 — 回归主路径空态

**Given** 无 owed 且无关闭日  
**When** 空首页  
**Then** S1 仍成立：主动作是添加资料（或账清态的单一主 CTA），工作流不升格为「假欠账列表」

### AC6 — 硬约束未动

**Given** 本夹改动  
**When** 跑相关检查  
**Then** 未改 `core/loop.py` gate、`core/schedule.py` 公式；无新 Agent/模型/推荐 API

## Test / gate

- 手测：AC1–AC5（空库 / 仅笔记 / 仅 due / due+plan / 收工）
- `cd web && npm run build`
- 若抽纯函数（owed 行组装），可加极小 unit；不强制后端 pytest

## SYSTEM 同步（实现时）

`docs/SYSTEM.md` Current main path：简报 = **欠练（due + 今日未核销计划）**；笔记可考不叫「欠」。一行即可。
