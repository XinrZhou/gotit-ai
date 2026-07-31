# chat-action-blocks — design

## Boundaries

| 动 | 不动 |
|----|------|
| 块 schema + Chat UI 渲染/点击 | 掌握门、排程 |
| 在已有 brief/tool/verify 路径**填充**块 | 新增大域后端产品 |

## Schema（示意）

消息 `metadata.action_blocks[]`（上限 **5**）。实现：`api/action_blocks.py`；
Web 类型：`ActionBlock` / `actionBlocksFromMeta`。

```json
{
  "action_blocks": [
    {
      "type": "owed_claim",
      "claim_id": "...",
      "title": "...",
      "due_reason_text": "...",
      "actions": [{ "id": "start_examine", "label": "开考" }]
    },
    {
      "type": "verdict",
      "gate_verdict": "almost",
      "claim_id": "...",
      "actions": [{ "id": "start_examine", "label": "再练" }]
    }
  ]
}
```

填充路径（最小集）：

| 来源 | 块 |
|------|----|
| companion `list_due_claims` | `owed_claim`（含 `due_reason_text`）→ 经 `_agent_metadata` 抬到消息 |
| examine / thread verify finalize | `verdict`（未过则带「再练」） |

点击走现有 `/v1/examine`、`/v1/drill/sessions` 等，与 tool trail 一键行为一致。

## UI

- 页私有组件：`ChatPage/ActionBlocks/`
- 样式：`--fill` 安静选中；无黑药丸；与 mastery chips / tool trail 纵向节奏一致
- 同一气泡块数量上限（5），防刷屏
- 气泡已有 `verdict` 块时不再叠 `VerifyVerdictChip`（避免重复吵闹）

## Risks

- 与 Bootcamp 并行：Bootcamp 应 import 本组件，勿复制一套按钮
- metadata 膨胀：只存 id + 短标签，不把整篇笔记塞进块
