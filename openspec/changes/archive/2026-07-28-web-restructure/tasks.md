# Tasks — web-restructure

- [x] 1. 安装 `sass` devDep；建目录 `src/pages`、`src/components`
- [x] 2. 抽共享文件：`types.ts`、`api.ts`、`format.ts`、`global.scss`
- [x] 3. `store.tsx`：StoreContext + useGotitStore（共享状态 + actions）
- [x] 4. 组件：`Avatars`、`Modal`、`Toast`、`SegmentedTabs`、`Sidebar`、`ChatLog`、`Composer`
- [x] 5. Modal 组件：`NoteComposeModal`、`ViewNoteModal`、`ProjectModal`（+ `YuqueNoteEditor` 移入文件夹）
- [x] 6. 页面：`ExaminePage`、`TeachPage`、`DrillPage`
- [x] 7. `Shell` 组合 sidebar + main-head + 当前 page + modals + toast
- [x] 8. 重写 `App.tsx`（StoreProvider + Shell）、`main.tsx`（import global.scss）
- [x] 9. 删除旧 `styles.css`、旧 `components/Avatars.tsx`、旧 `YuqueNoteEditor.tsx`
- [x] 10. `npm run build` 通过 + 浏览器手测
- [x] 11. sync openspec + 归档 web-restructure
