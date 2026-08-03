# Design: main-path-converge

## North star (working agreement)

| Do | Don't |
|----|--------|
| 收「打开 → 过一关」摩擦；立意可感 | 默认加新脊柱机制 / 更深 Agent 平台 |
| 温度 × 较真同一张脸 | 鸡血催更或模型哄「你学会了」 |
| 机制能藏就藏 | 为机制找 Settings 安放 |
| 外围只挂主线 | 拼盘展览、同质学习助手 |

## Product story（长期北星）

> 愿意天天打开的验证型搭子：有温度地陪你，但「会不会」只认证据。

主线唯一：

```text
今天欠什么 → 认真验一次 → 过了/还差点/欠着下次 → 失败留痕 → 下次带着教训来
```

与市面差异：不是家教 Chat、不是 Anki+LLM、不是 multi-agent demo。

## Product story 验收清单

| # | 验收 | 怎么算过 |
|---|------|----------|
| S1 | 空态有主动作 | 有欠账 → 简报开练是主；无欠账 →「添加资料」为主，工作流降级 |
| S2 | 深挖叙事诚实 | 入口/ModeHeader/开场均暗示「练习场，不过门·不算掌握」 |
| S3 | 过关可感 | 芯片用语统一：过了 / 还差点 / 欠着下次；过了有安静旁注 |
| S4 | 出题→开考不断 | IngestOutcome「去开考」文案服务「过门才算会」 |
| S5 | 一日节奏有温度 | 欠账标题/收工/空闲态人话，不堆功能墙 |
| S6 | 考/回讲对称 | 选题列表不截断；空态可「添加资料」；门禁用语一致 |
| S7 | 气泡动作诚实 | ActionBlocks「练深挖」+ verdict 旁注；深挖结束明示不过门 |
| S8 | 旁路文案不抢戏 | 摸底/资料/面试设置不暗示「深挖=会了」 |

## Current main path (truth)

```text
打开 App
  → 空聊天 / 今日简报（欠练 + 计划；有则一键开练）
  → 无料时：添加资料 → 出题 →「去开考」
  → 考我 / 回讲（Critic + deterministic_gate）
     · 深挖 = 项目练习场（不过门，不算掌握）
  → 芯片：过了 / 还差点 / 欠着下次
  → 欠清或主动「今日收工」
```

旁路（不强化）：弱点图谱、Settings、Apple 桥、Harness API/CLI、CAT 写回。

## Archive policy (task 0)

已执行 → `archive/2026-08-03-*`。Current active 仅 `main-path-converge/`。

## Visual

遵守 `ui-apple.mdc`：安静选中；打磨以层级与文案为主。

## Test / gate

- 手动主路径走查 + 本清单 S1–S5
- `cd web && npm run build`；改共享行为则相关 pytest
