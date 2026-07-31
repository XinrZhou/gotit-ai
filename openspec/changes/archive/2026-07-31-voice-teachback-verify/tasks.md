# voice-teachback-verify — tasks

## A — Backend

- [x] 转写适配（可先 stub + 文本路径）
- [x] teach 提交对齐共享 finalize / 同档位语义
- [x] REST（+ MCP 可选）；单测文本路径

## B — Web

- [x] Teach 工作流：录音或粘贴转写 → 确认 → 提交
- [x] 无 STT 时隐藏录音、保留文本
- [x] 结果展示与 examine 芯片一致（读 metadata）

## C — Docs / gate

- [x] pytest；相关 web 不破 build
- [x] `docs/SYSTEM.md` 一句
