# voice-teachback-verify — design

## Boundaries

| 动 | 不动 |
|----|------|
| teach 口说 → 转写 → 既有 teach/verify 写回 | examine 主流程重写 |
| 应用内入口 | 渠道-only 实现 |

## Flow

```text
选择 claim → 开始回讲
  →（可选）音频 → STT 转写
  → Echo teach 评分路径
  → Critic（若 teach 已接）+ deterministic gate / 既有 teach verdict 对齐 finalize
  → trajectory / failure_digest / 再练
```

若当前 teach 尚未接共享 `verify_finalize`，本 change **对齐到同一终审模块**，禁止教路径旁路门禁。

## Config

- `STT_*` 或复用 `LLM_*` 兼容接口；缺省 → UI 只开文本回讲

## Risks

- 转写质量差：允许用户改稿再提交
- 时长/费用：单次时长上限；不自动连录
