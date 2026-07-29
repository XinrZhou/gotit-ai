# chat-shell — Chat 壳布局 + 对话交互打磨

## Why

中间栏塞了品牌 / 资料库 / 工作流 / 线程，资料库再开第三列会挤聊天区；同时
对话体验偏「等接口再出字」——新对话弹窗打断、历史不能删、无思考中态。
应对齐 Apple Notes/Mail 式安静壳 + 市面常见 agent 聊天交互。

## Scope

### In — layout

- Library = **左侧抽屉 overlay**（不推开聊天列）
- Nav rail：品牌 + day + 资料库 + 线程；**工作流移到对话顶栏**
- Composer：@agents / skills 收进 **`+` tray**
- Thread 行：标题 + 时间一行；窄屏 nav → icon rail
- Library 空态：单一空块 + 主 CTA

### In — interaction

- `DELETE /v1/threads/{id}` + MCP 对等
- 新对话无 `prompt`；标题「新对话」；首条用户消息后启发式回写标题
- `ChatTurn.thinking` → `metadata.thinking`；前端可折叠
- 乐观用户气泡 +「思考中」占位；历史可删
- 打开对话时 @搭子默认选中该 thread 最后聊过的搭子
- 聊天身份卡；chat 路径不注入 examine rubric

### Out

- 真流式 SSE/token 推送
- LLM 生成标题（启发式即可）
- 改 verify API / agent 路由语义

## Verification

- `uv run pytest`（相关）+ `cd web && npm run build`
- 手动：抽屉不挤列；工作流在顶栏；新对话无弹窗 → 首句改标题；发送即见气泡；可删历史
