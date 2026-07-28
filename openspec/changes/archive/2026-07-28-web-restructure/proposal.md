# web-restructure — 前端目录与模块化重构

> **Status: proposed 2026-07-28**

## Why

当前前端 `App.tsx` 单文件 1300+ 行，混入了 sidebar、三种模式（考我/回讲/项目深挖）、多个 modal、toast、项目/笔记逻辑，样式全堆在 `styles.css` 全局类里，没有边界、没有拆分，难维护。

按统一规范重构：页面进 `src/pages/<PascalCase>/`，组件进 `src/components/<PascalCase>/`，每个文件夹只有 `index.tsx` + `index.module.scss` 两个文件，子组件按需拆成子文件夹（同样两文件）。样式用 CSS Modules 收敛作用域，全局只保留 tokens / resets / 跨组件工具类。

## Scope

### In

- 目录结构：`src/pages/<Name>/{index.tsx,index.module.scss}`、`src/components/<Name>/{index.tsx,index.module.scss}`
- 共享逻辑抽到 `src` 根的扁平文件：`types.ts`、`api.ts`、`format.ts`、`store.tsx`（StoreContext + `useGotitStore`）
- 全局样式 `src/global.scss`：tokens、resets、`button:disabled`、第三方编辑器 `.yuque-note-editor`、注入内容 `.note-body`、跨组件按钮/输入工具类
- 组件拆分：`Shell`、`Sidebar`、`SegmentedTabs`、`ChatLog`、`Composer`、`Modal`、`Avatars`、`NoteComposeModal`、`ViewNoteModal`、`ProjectModal`、`Toast`
- 页面拆分：`ExaminePage`、`TeachPage`、`DrillPage`
- `App.tsx` 只做 `StoreProvider + Shell` 组合
- 引入 `sass` devDep，Vite 原生支持 `.module.scss`

### Out

- 后端、MCP、OpenSpec 流程不变
- 行为/交互不变（考我主题 session、回讲、项目深挖、modal 流程全部保留）

## Non-goals

- 不引入路由库（仍是单页 mode 切换）
- 不引入状态管理库（用 Context + 自定义 hook）
- 不改设计风格 / 不换色

## Verification

- `npm run build` 通过（tsc + vite）
- 浏览器手测：sidebar 项目 chip + 笔记列表 + 添加资料 modal；考我主题 session 对话；回讲；项目深挖卡片 + 对话；编辑/新建项目 modal；toast
- 后端 gate 不受影响
