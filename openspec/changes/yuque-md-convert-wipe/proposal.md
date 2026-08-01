# Yuque compose polish (md convert + shell)

## Why

「添加资料」手写粘贴 Markdown 后点「立即转换」，编辑器正文被清空。
受控 `value`/`onChange` 与语雀库内 sync 在转换中间态空 `contentchange` 上打架。

同屏弹窗偏窄、编辑区偏矮，长文写作吃力，需要加宽与放大预览。

## What changes

- `YuqueNoteEditor`：`value` 只作初始种子；空闪烁 onChange 延后确认
- `NoteComposeModal`：不再受控同步 HTML；读写走 ref
- 弹窗默认加宽；手写区支持「放大预览 / 收起」（CSS 扩壳，不 remount 编辑器）

## Out

- 链接 / 文件导入 tab
- 升级或 fork `yuque-editor-core`
