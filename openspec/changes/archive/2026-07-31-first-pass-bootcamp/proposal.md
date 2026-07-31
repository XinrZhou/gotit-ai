# first-pass-bootcamp

## Why

新用户若摸不到「笔记 → claim → 开考 → 过门」完整证据链，产品会停在 agent 演示感，不愿意天天打开。

对应 `docs/PRODUCT.md` 演进 §6：第一周就跑通证据链。

## What changes

| 块 | 内容 |
|----|------|
| A | 空库（或几乎空）检测 + 步进状态（可 memory / day 标志） |
| B | 引导：导入或贴一段笔记 → 抽出 claim → 开考（或轻摸底）→ 展示结果芯片/轨迹 |
| C | 复用 `chat-action-blocks` 原语；若 C 未合入则用简易 CTA，合入后切换 |
| D | 可跳过；不强制每次打开 |

## Out

- 长教程 / 幻灯片 onboarding
- 改 gate 或校准算法本身（可**调用**既有 calibration）
- 多用户、账号体系

## Acceptance

空库用户三条内可完成一次带门禁结果的验证；跳过后不再纠缠；已有数据用户不打扰。

## Agent owns / do not touch

- **Owns:** Bootcamp 状态机、SessionStart / 空态文案与步进 UI、标志位 API
- **Do not touch:** 重写 ActionBlocks 原语（只消费）、digest 晋升、schedule 内核、面试 ramp
- **Depends:** 优先等 `chat-action-blocks` 合入；若并行，先简易按钮，预留替换点
