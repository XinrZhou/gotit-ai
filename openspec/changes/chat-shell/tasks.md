# chat-shell — tasks

## Spec

- [x] proposal / design / tasks（合并自 `companion-layout` + `chat-ux`）

## Layout

- [x] Library always absolute overlay；desktop does not push `main`
- [x] Scrim whenever open
- [x] Remove workflow tabs from nav rail；conversation top bar chips
- [x] Thread row: title + time one line
- [x] Composer `+` tray for agents/skills
- [x] Narrow: icon-rail styles
- [x] Library empty block + CTA
- [x] Touch `docs/SYSTEM.md` layout note

## Interaction

- [x] `delete_thread` / `update_thread_title` + barrel；`DELETE /v1/threads/{id}`；MCP
- [x] `ChatTurn.thinking` + prompt；metadata；`AgentReply.thread`；首条提炼标题
- [x] ChatPage：无弹窗新对话；乐观发送 + 思考中；thinking 折叠；删除历史
- [x] 聊天身份卡 + 不注入 examine rubric
- [x] 打开对话时 @搭子默认选中最后聊过的搭子
- [x] `cd web && npm run build`；相关 pytest
