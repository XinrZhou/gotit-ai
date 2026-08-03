# Tasks: verify-return-loop

> 验收：`design.md` AC Case 1–5。禁止改 gate / schedule / 新 Agent。  
> 完成后先真用观察，**不默认开 P0-3**。

## 1. Spec lock

- [x] 确认 done 态只消费已有 writeback / verify 字段
- [x] 确认主 CTA = 回今天；almost 可有接着练
- [x] 确认 Drill 不在本夹改过门叙事以外的大改

## 2. Data on the wire

- [x] 核对 examine/teach JSON：`writeback.claim.next_review_at`、`schedule_reason`、`interval_days`、`verify.gate.reason`
- [x] 前端类型补全；store 在 session_done 保留 last outcome 摘要
- [x] 若缺字段：仅 API 透传已有 ops 返回值（不改算法）— 无需新 API

## 3. UI

- [x] Examine session_done：Done 条（结果已有芯片可并列）+ 影响一行 + CTA
- [x] Teach claim-bound done：对称
- [x] 「回今天」→ `setMode("chat")` + 清 examine/teach session；依赖已有 refresh
- [x] almost：「接着练」最小实现
- [x] Apple quiet select；无成就/报告页

## 4. Docs

- [x] `docs/SYSTEM.md`：考完 → 回今天看欠账/账清（一句）
- [x] `openspec/changes/README.md` 挂 active（本夹）

## 5. Gate

- [ ] 手测 Case 1–4（passed / almost / owe_next / 回 Brief）
- [x] `cd web && npm run build`
- [ ] 提交（用户要求时）单独故事：`fix(web): return to today after verify`（勿与 6.1/P0-3 混）

## Out / Later

- [ ] P0-3 入口降噪 — **真用观察后再开**
- [ ] Drill finalize；AI 总结报告
