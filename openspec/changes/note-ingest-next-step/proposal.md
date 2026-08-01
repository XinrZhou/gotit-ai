# Note ingest → next step

## Why

「出题」完成后只剩 toast，用户不知道下一步；出题中也几乎没有可见进度。断点在
笔记 → claim，不在开考本身。

## What Changes

- 添加资料「出题考我」、查看笔记「出题」：`generating` → `ready` 三态
- 出题中留在当场，文案「正在出题…」
- 出好后结果卡 + 主按钮「去开考」（第一条 claim）+「先不考」
- 复用现有 `startExamineClaim` 进考场；不自动开考

## Out

- 侧栏「一键出题」进度条（仍可 toast；下刀再补）
- 改 Compass / gate / 排程
- 自动开考无确认
