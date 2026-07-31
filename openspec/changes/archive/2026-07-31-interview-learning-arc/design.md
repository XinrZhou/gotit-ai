# interview-learning-arc — design

## Boundaries

| 动 | 不动 |
|----|------|
| 今日简报 / 空态组装逻辑 | ramp 分档公式 |
| 一键深挖（现有 API） | 新推送通道 |

## Brief 规则

读取 upcoming interview + `ramp_tier` + ramp prefs：

| tier | 简报 |
|------|------|
| silent / past | 不展示面试偏置 |
| light | 一行安静提示 + 可选深挖 |
| warm / urgent | 更靠前的「建议项目深挖」条；仍不盖过 owed 列表首屏逻辑时可并列 |

`enabled=false` → 无偏置条；upcoming 仍可在 Settings 见。

## Copy

- 人话、短：「面试还有 3 天，今天要不要抠一下「某某项目」？」
- 不使用恐吓或鸡血

## Risks

- 与 owed 开考抢注意力：欠账仍在；深挖是并列建议不是替换验证脊柱
- 与 day-close：收工后弱化开考，深挖建议同样降级为安静链接
