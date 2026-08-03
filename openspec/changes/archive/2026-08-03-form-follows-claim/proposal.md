# Proposal: form-follows-claim

## Why

VISION P3 / PRODUCT §7：验证形态应跟主张走。`CheckMode`
（probe / drill / apply / teach_back）已在模型层存在，但今日欠账、
action_blocks、一键入口一律进 examine，回讲/深挖要靠人手点工作流。

## What changes

1. Claim 可选 `preferred_check_mode`（落库；null = 默认 probe）。
2. 确定性 `resolve_check_mode` / `route_verify_action`（framework-free）：
   选 CTA 与 open-*，**不改** Critic + deterministic gate。
3. 今日欠账 / action_blocks / companion `start_verify` 按形态分流
   （开考 / 回讲 / 深挖）；ingest 可用轻量启发式建议 mode。
4. `PATCH /v1/claims/{id}` 可改偏好（人仍是 judge）。

## Out

- 完整 APPLY 工作流（v1 降级 probe）
- Compass LLM 自动标 mode
- drill 按 claim_id 走 gate 关门（深挖仍是项目会话入口）
- 改排程 / FSRS / CAT 参数

## Impact

- alembic `0014_claim_preferred_mode`；`core/check_routing.py`
- REST + companion + DailyBrief / ActionBlocks CTA
- tests：`test_check_routing.py` + action_blocks 扩展
- `docs/SYSTEM.md` 补一句 shipped
