# Tasks — UI layout rework

- [x] 1. 开 openspec/changes/ui-layout-rework/（proposal/design/tasks）
- [x] 2. 重构 `web/src/App.tsx`：双栏（资料/验证）+ segmented[考我/回讲] + 笔记⋯菜单 + 拆分添加入口 + 空状态引导
- [x] 3. `web/src/styles.css`：新增 segmented / ⋯ 下拉菜单 / 题选择条 / 分区强化样式
- [x] 4. 验证：`npm run build` + ruff/mypy/pytest 全绿
- [x] 5. sync openspec 并归档 ui-layout-rework

## Delivery notes

- 仅改前端两个文件：`web/src/App.tsx`、`web/src/styles.css`，后端零改动。
- 左栏改为「今日资料」：笔记列表为主体（flex 撑满），每条右侧 ⋯ 下拉菜单（查看 / 整理成测验 / 删除），底部「+ 添加资料」。
- 右栏改为「今日验证」：顶部 segmented `[考我 · N] [回讲]`；考我模式含横向题选择条 + 对话 + composer，右上角「+ 手动加题」「补回顾」；回讲模式内联（原 modal 废弃）。
- 「添加测验」modal 拆分：资料 modal 仅留 [手写/链接/文件] 并加说明文案；手动加题独立 modal；补回顾降级为考我模式右上按钮。
- 空状态引导：左栏无资料 / 考我无题 / 回讲空 均有文案。
- `showTeach` state 与 `onOpenTeach` 已删除（回讲内联右栏）；新增 `mode` / `openMenuId` / `showManual` 三个 state。
- 验证：`npm run build` 通过（tsc + vite）；`ruff check . && mypy src && pytest` 全绿（7 passed），确认未误改后端。
