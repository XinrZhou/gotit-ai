# first-pass-bootcamp — design

## Boundaries

| 动 | 不动 |
|----|------|
| 引导状态与空态步进 | gate、Critic、schedule 公式 |
| 调用既有 ingest / examine / calibration | 新造第二套验证 |

## Steps

1. `detect`: claims==0 且 notes 很少 → 显示引导（非每次）
2. `ingest`: 粘贴/导入 → 抽 claim
3. `verify`: 一键开考或「先摸底一下」（已有 calibration CTA 可衔接）
4. `celebrate_quietly`: 展示过了/还差点 + 轨迹；写 `bootcamp_done`

可跳过 → `bootcamp_skipped`；不再强弹。

## UI

- 放在 SessionStart / 空聊天，不新开信息架构页
- 文案人话，不堆概念（「先拿一段笔记，我们抽出能考的一句」）

## Risks

- 与冷启动校准 CTA 抢入口：引导里显式二选一或串成一步，避免两个大按钮互抢
- 与 day-close：Bootcamp 日不强调收工
