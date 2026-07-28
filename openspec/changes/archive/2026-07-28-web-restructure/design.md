# Design — web-restructure

## 目录

```
web/src/
  main.tsx              # 入口，import global.scss
  App.tsx               # <StoreProvider><Shell/></StoreProvider>
  global.scss           # tokens/resets/全局工具类
  types.ts              # 共享类型
  api.ts                # api client + API_BASE/API_KEY
  format.ts             # todayISO/stripHtml/fmtDate
  store.tsx             # StoreContext + useGotitStore（共享状态 + actions）
  components/
    Avatars/            index.tsx + index.module.scss
    Shell/              布局壳：sidebar + main-head + 当前 page + modals + toast
    Sidebar/            项目 chip + 笔记列表 + 添加资料按钮
    SegmentedTabs/      考我/回讲/项目深挖 切换
    ChatLog/            气泡列表（examine/teach/drill 共用）
    Composer/           输入区（textarea / topic-input 两种 kind）
    Modal/              浮层基座（overlay/modal/head/close/actions/body）
    NoteComposeModal/   添加资料（write/link/zip）
    ViewNoteModal/      查看笔记
    ProjectModal/       新建/编辑项目
    Toast/              error/flash
  pages/
    ExaminePage/        主题 session 聊天
    TeachPage/          回讲
    DrillPage/          项目深挖
```

每个文件夹只有 `index.tsx` + `index.module.scss`；子组件需要时拆子文件夹（同样两文件）。

## 状态归属

- **Store**（共享）：day、plan、notes、projects、selectedProjectId、mode、busy、error、flash、refresh、run；examine/teach/drill 对话状态与 actions；viewNote + open/delete/ingest；showCompose、showProjectModal + editingProject + openers；openMenuId。
- **Modal 本地**：表单字段（NoteComposeModal 的 noteHtml/noteTitle/importTab/linkUrl + editor ref；ProjectModal 的 projName/role/goal/stack）。保存时调 store action。

## 样式作用域

- `global.scss`：`:root` tokens、`*`/`body`、`button/input/textarea`、`button:disabled`、`.yuque-note-editor`(第三方需全局)、`.note-body`(+`p`，注入 HTML)、按钮工具类 `.btn-ghost/.btn-ink/.btn-danger/.btn-compose/.btn-danger-ghost/.btn-delete-item`、输入工具类 `.note-title-input`、`.muted`。
- 其余类全部进各组件/页面的 `.module.scss`，JSX 用 `styles.x`。
- 跨组件复用的小类（按钮/输入/muted）保留全局，避免每个模块重复定义。

## 组件接口要点

- `ChatLog({ messages, examinerAvatar, examinerName, empty })`：渲染气泡 + 自动滚底（内部 ref）。
- `Composer({ kind, value, onChange, placeholder, onSubmit, submitLabel, busy, disabled })`：kind="textarea"|"topic"。
- `Modal({ title, onClose, children, actions })`：基座。
- `SegmentedTabs({ mode, onChange, counts })`。
- `Sidebar`：从 store 取 projects/notes/day，触发 store actions。

## Risks

- CSS Modules 转换漏类 → 仔细对照 className 清单，build 后浏览器手测补漏。
- 第三方编辑器依赖全局 `.yuque-note-editor` → 保留在 global.scss。
- 注入 HTML（`.note-body p`）无法被 module 选中 → 保留全局。
