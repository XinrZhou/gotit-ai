# Proposal: daily-brief-semantic-cleanup

## Why

DailyBrief（「今天还欠这些」）当前把三类东西混在同一列表：

1. **Due claim** — `due_claims`（排程/状态决定的今日欠练）
2. **Plan-open claim** — 今日计划里未核销、且不在 due 集合的 claim
3. **Note claim** — 任意带 `claim_ids` 的笔记（「库里还能考」）

首页是否展示 Brief 也用同一混合条件（`hasDailyBrief` 含「有笔记带 claim」）。

结果：**「欠」字失真**——用户无法相信列表上每一项都是今天真正该处理的事项。  
Phase6 目标不是加能力，而是让已有验证闭环成为可信日课；本夹只修简报语义。

父夹 `main-path-converge/` 近归档（S1–S8 UX）；本夹是其 Phase6 P0 续作，**独立 Why / Out**，故新开文件夹而非塞进待归档夹。

## What changes

- Brief **默认只列真正「今天欠」的行**：due +（可选）今日未核销且绑定 claim 的 plan item
- 笔记「可考」**不得**顶着「今天还欠」标题出现；无欠时走空闲/账清语义，而不是假 Brief
- `hasDailyBrief`（或等价）与标题文案与上对齐
- 文档短同步：`docs/SYSTEM.md` 主路径一句；必要时 README 不改（无 pitch 漂移可不碰）

## Out（明确不做）

- 新模型 / 新 Agent / 新推荐系统 / 新排序学习
- 改 `deterministic_gate` 或 `core/schedule.py` 公式
- 改 examine/teach finalize、failure 写回、mastery graph
- 新 API / 新领域字段（除非现有 today 字段文案不够——默认不扩）
- P0-2 考完回程、P0-3 入口抢戏（后续夹）
- Examine/Teach 选题页大改（可随后对称，本夹不强制）
- 视觉大改（已有 `daily-brief-polish`）；本夹以列表组成与文案为准

## Success

用户打开空首页时：

> 系统展示的「欠」一定是真正需要处理的事项。

无 due（且无合格 plan-open）时，**不会**再看到标题为「今天还欠这些」却塞满笔记行的假欠账。

## Impact

- 主要：`web/src/components/DailyBrief/`、`web/src/pages/ChatPage/`（`hasDailyBrief` / 空态分支）
- 次要：`docs/SYSTEM.md` 一句；可选组件测 / 手测清单
- 无 Postgres / gate / schedule 算法变更
