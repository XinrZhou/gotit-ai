# Tasks — yuque-md-convert-wipe

- [x] `YuqueNoteEditor`：冻结 seed；空 onChange 延后确认
- [x] `NoteComposeModal`：去掉 `noteHtml` 受控；保存/清空走 ref
- [x] 弹窗加宽 + 手写放大（底栏安静图标，`Modal.fill`，不 remount）
- [x] 操作区钉在 `Modal.actions`，去掉悬空「放大预览」文案
- [x] `setFlash` 约 2.4s 自动清除（「笔记已保存」不再常驻）
- [ ] 手测：粘贴 Markdown →「立即转换」→ 正文保留 → 放大/收起正文仍在 → 可「出题考我」
