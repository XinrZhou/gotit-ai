# Design: main-path-converge

## North star (working agreement)

| Do | Don't |
|----|--------|
| 收「打开 → 过一关」摩擦 | 默认加新脊柱机制 |
| 机制能藏就藏 | 为机制找 Settings 安放 |
| 归档已 ship 的 OpenSpec | 让活跃夹无限堆积 |

## Current main path (truth for this wave)

```text
打开 App
  → 空聊天 / 今日简报（欠练 + 计划；有则一键开练）
  → 无料时：添加资料 → 出题（generating → ready）→「去开考」
  → 考我 / 回讲（preferred_check_mode 分流；Critic + deterministic_gate）
     · 深挖 = 项目练习场（可写 thread；不过门，不算掌握 — 文案勿暗示「过关」）
  → 芯片：过了 / 还差点 / 欠着下次
  → 欠清或主动「今日收工」
```

旁路（本波次不强化入口）：弱点图谱、Skills/MCP、计划推送、动态、Apple 桥、
Harness API/CLI、CAT 题参写回（后台吃即可）。

## Archive policy (task 0)

归档候选（代码已在 main、夹仍在 active 时）：

| Folder | 归档条件 |
|--------|----------|
| `verify-spine-deepen/` | gate signals + ContextBudget + harness REST 已合；Settings UI 已撤 |
| `form-follows-claim/` | preferred_check_mode 路由已合 |
| `cat-param-writeback/` | calibration 写回已合 |
| `note-ingest-next-step/` | 出题 → 去开考已合（含后续 thread UX 抛光） |
| `daily-brief-polish/` | 若 brief 抛光已合 main |
| `yuque-md-convert-wipe/` | 若语雀转换修复已合 main |

归档命名：`archive/2026-08-03-<name>/`（已执行）。更新
`openspec/changes/README.md` Current active → 仅剩 `main-path-converge/`。

## Friction audit (how to work)

1. 用**空库或接近空库**账号走一遍主路径；再用不为空、有欠账账号走一遍。
2. 每卡一下记一条：`哪里 / 现在文案或控件 / 期望`。
3. 只收清单上的项；诱惑性机制需求丢进「Later」，不进本 tasks。

## Likely polish surfaces (not exhaustive — audit first)

- SessionStart / DailyBrief / bootcamp 文案与 CTA 优先级
- IngestOutcome「去开考」与 preferred mode（回讲/深挖）措辞是否一致
- 工作流顶栏 / ModeHeader「正在…」是否吵
- 设置页：学习者用不到的词是否可降噪（不删能力）
- 空聊天 vs 有 thread 时 brief 是否重复或失踪

## Visual

遵守 `ui-apple.mdc`：安静选中、不加响亮铬条；打磨以层级与文案为主，
不引入新色板。

## Test / gate

- 以手动主路径走查为主（本波次少新单测）
- 若改共享组件行为：相关现有 pytest / 前端不破
- 收工前：`./scripts/gate.sh` 或至少 `uv run pytest -q` + `cd web && npm run build`
