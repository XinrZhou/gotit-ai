# chat-action-blocks

## Why

今日欠账、工具轨迹、门禁结果已在对话里出现，但多为长文或弱按钮，办事仍要点来点去。需要**可点的结构块**把「看到 → 开考」缩成一步，仍挂在验证脊柱上。

对应 `docs/PRODUCT.md` 演进 §1：工具少而准、对话里可点块办事。

## What changes

| 块 | 内容 |
|----|------|
| A | 消息 `metadata` 约定：`action_blocks[]`（type / payload / label） |
| B | Web：欠账卡、门禁结果卡、一键开考/深挖（安静 Apple 样式） |
| C | 服务端在 brief / tool 结果 / verify 写回时填充块（最小集） |
| D | 与现有 tool trail / mastery chips 共存，不重复吵闹 |

## Out

- 通用富文本编辑器、代码 diff 卡
- Mission 式仪表盘
- 改 gate 语义
- Bootcamp 文案步进（归 `first-pass-bootcamp`，本 change 只提供原语）

## Acceptance

空态或 companion 工具返回欠账时，用户可在气泡内一点开考；verify 结束后结果卡展示档位且不解析纯文案；视觉符合 ui-apple（安静选中）。

## Agent owns / do not touch

- **Owns:** `web` Chat 消息块组件、metadata 类型、服务端填充块的最小挂钩（examine/tool 结果）、测/Story 级手工验收点
- **Do not touch:** digest 晋升、收工 API、schedule 公式、Bootcamp 多步状态机（D 可消费本原语）
