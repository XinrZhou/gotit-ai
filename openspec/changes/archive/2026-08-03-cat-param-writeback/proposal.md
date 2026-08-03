# Proposal: cat-param-writeback

## Why

Cold-start CAT-lite 已有 2PL 选题与 θ 更新，但多数 claim 的
`difficulty` / `discrimination` 仍停在缺省。日常 verify 与摸底的结果
没有反哺题参，下一轮选题仍像「全是难度 3」。

## What changes

1. 确定性 `update_item_calibration`：用 gate / 摸底二元结果更新
   `claims.calibration`（难度、区分度、attempt 计数）——无 LLM。
2. 接线：共享 `finalize_examine_with_gate` + `answer_calibration`。
3. 单测钉死步长、裁剪与「挂→变难 / 过→变易」。

## Out

- 工业级 IRT 联合估计 / EM
- 按学习者个人 θ 做题参更新（v1 用 θ=3 参考算 surprise）
- 前端题参编辑 UI
- 改 schedule / gate 语义

## Impact

- `gotit.core.calibration` + `db.ops` writeback；无新表
- `docs/SYSTEM.md` Not-done → shipped
- tests：`test_calibration_core` 扩展 + 轻量 ops 测
