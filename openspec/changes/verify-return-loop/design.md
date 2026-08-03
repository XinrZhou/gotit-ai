# Design: verify-return-loop

## 1. Problem Statement

### 用户完成验证后看到什么（现状）

- Examine/Teach 会话内：最后一轮气泡 + `VerifyVerdictChip`（过了 / 还差点 / 欠着下次）+ 旁注 +「这轮考完了」
- 可选 `VerifyTrajectory`（考→核→门）挂在气泡上
- **Composer 关闭**；无底部下一步
- 顶栏仅有 ModeHeader「← 搭子」

### 缺少什么

| 缺失 | 影响 |
|------|------|
| 这次结果如何改变排程/欠账 | 感觉「聊完了」而非「路径变了」 |
| 明确「回今天看欠账」 | 须发现返回键；Brief 已 refresh 但看不见 |
| 档位差异化下一步 | almost 想接着练时无主动作 |
| gate.reason / writeback 排程对人可见 | 数据在响应里，UI 几乎不用 |

### 为何影响长期使用

日课留存依赖「做完一关 → 看见账变了 → 知道下次」。断在回流 → 验证变成孤立会话，打开 App 的理由变弱。

---

## 2. Current Flow Audit

```text
用户提交答案
  ↓
Axiom / Echo（LLM 表现）
  ↓
Critic 复核
  ↓
deterministic_gate
  ↓
apply_examine_verdict + trajectory + fail/failure_digest + …
  ↓
API 返回 verdict + writeback + verify（含 gate.reason）
  ↓
UI：芯片 +「这轮考完了」；refresh() 更新 store
  ↓
下一步：❌ 无 CTA — 用户卡在空 Composer 的会话壳里
```

**断点：** `examineSessionDone === true`（Teach 对称 done）之后 → 回到已更新 DailyBrief / 账清 之间。  
数据已写；**感知未接上。**

---

## 3. Desired User Flow

```text
验证完成（同一会话，不新开「报告页」）
  ↓
结果：passed | almost | owe_next（芯片，已有）
  ↓
解释：为何此档（gate.reason 人话 / 轨迹已有；不新增 LLM 终审）
  ↓
影响：写回后的状态与排程（claim.status、next_review_at、schedule_reason / interval_days）
  ↓
下一步：
  · 主：回今天（见最新 Brief / 账清）
  · almost 次要：接着练（同 claim 再开一轮，可选）
```

**原则：** 不增加「多一步向导」；在 done 态用安静条补全信息 + CTA，替代空白。

---

## 4. Scope

### In Scope

- Examine（及 claim-bound Teach）**session done** 底部/尾部 UI
- 展示**已有**字段：`gate_verdict`、`verify.gate.reason`（或轨迹）、`writeback.claim`（status / `next_review_at`）、`writeback.schedule_reason` / `interval_days`（若响应已带）
- 主 CTA **回今天**：`setMode("chat")` + 清 session 状态，落到空首页（Brief 或账清，依赖 6.1）
- almost：**接着练**（重置同 claim 会话或一键再开 examine）— 最小实现即可
- 前端类型：补全 writeback 已有键，避免丢弃
- `docs/SYSTEM.md` 主路径加「考完 → 回今天」一句
- 手测 AC；`npm run build`

### Out Scope

- 修改 gate / mastery / schedule / failure 规则或 Claim schema
- 新 Agent / 模型 / 成长报告 / 成就 / 新表
- 新推荐、自动挑下一题（「全部」仍走现有 Brief/picker）
- Drill done 叙事大改（可一行「不过门」维持现状）
- P0-3 入口降噪
- 强制新 REST；仅当现有 writeback 缺展示字段时才薄补 **透传**（算法不变）

---

## 5. State Mapping（全部来自已有数据）

模板用语安静、非鸡血；数字/日期来自 writeback，禁止前端发明间隔。

### passed

| 展示 | 来源 |
|------|------|
| 结果：过了 | `gate_verdict` |
| 为何：有证据 / gate.reason | `verify.gate.reason`；旁注已有「有证据了」 |
| 影响：已掌握；今日该条不再欠 | `claim.status=mastered`；`next_review_at` 通常 null → 文案「这条先清了」 |
| 下一步 | **回今天**（看是否还有欠 / 账清） |

### almost

| 展示 | 来源 |
|------|------|
| 结果：还差点 | `gate_verdict` |
| 为何：未完全过门 | `gate.reason`（含 score/evidence 降档信号时已在 reason 串里） |
| 影响：今天还接着 | `next_review_at = today` / `schedule_reason=almost_today` |
| 下一步 | **接着练**（次要或并列安静）+ **回今天** |

### owe_next

| 展示 | 来源 |
|------|------|
| 结果：欠着下次 | `gate_verdict` |
| 为何 / 教训 | `gate.reason`；若有 failure_digest 相关提示用已有 hint（无则不强造） |
| 影响：改日再碰 | `next_review_at` + `interval_days` / `schedule_reason=owe_scheduled` → 「约 X 天后 / 某日再考」 |
| 下一步 | **回今天**（看其余欠账）；不默认立刻再开同一题 |

不创造第四种 mastery 状态。

---

## 6. Acceptance Criteria

### Case 1 — passed

**Given** claim-bound examine/teach 过门为 `passed`  
**When** session_done  
**Then** 可见结果芯片；可见排程/状态影响（如「这条先清了」或等价，基于 writeback）；可见 **回今天**；点后离开工作流，空首页 Brief/账清反映该 claim 已不在 owed

### Case 2 — almost

**Given** gate = `almost`  
**When** session_done  
**Then** 可见「还差点」与今日仍欠/接着的含义（基于 schedule_reason 或 next_review）；可见 **继续练**（或同等）与 **回今天**

### Case 3 — owe_next

**Given** gate = `owe_next`  
**When** session_done  
**Then** 可见「欠着下次」；可见后续安排（日期或间隔，来自 writeback，非 LLM）；可见 **回今天**

### Case 4 — 返回后 Brief

**Given** 用户点「回今天」且 store 已 refresh  
**When** 回到 chat 空首页  
**Then** DailyBrief / 账清与 6.1 语义一致，且反映刚完成的写回（该条从 owed 消失或 almost 仍在）

### Case 5 — 硬约束

**Then** 未改 `core/loop.py` gate 逻辑、`core/schedule.py` 公式；无新 Agent/表；Drill 仍不过门

---

## 7. Implementation Plan（最小）

| 层 | 是否需要 | 说明 |
|----|----------|------|
| 前端 | **是** | Done 条组件（可挂 ExaminePage/TeachPage 底部或 ChatLog 下）；接线 writeback；回今天清 session + `setMode("chat")` |
| Store | 轻 | `useExamine`/`useTeach` 在 done 时保留 last writeback/verify 摘要供 UI |
| API | **默认否** | 确认 examine/teach 响应已含 `writeback.schedule_reason`/`interval_days`/`claim.next_review_at` 与 `verify.gate`；缺则只透传，不改算法 |
| DB / core | **否** | — |
| 测试 | 手测 AC1–4 + `cd web && npm run build`；可选组件 smoke | 不强制新 harness case |

### 建议触碰文件（实现时）

- `web/src/pages/ExaminePage/`（+ Teach 对称）
- `web/src/store/useExamine.ts` / `useTeach.ts`
- 可选小组件 `web/src/components/VerifyDoneBar/`（或 page-private）
- `web/src/types` writeback 类型
- `docs/SYSTEM.md`
- OpenSpec tasks 勾选

### 明确不做

大重构 ChatPage、新路由、新领域包、P0-3。

---

## Post-ship（本夹外执行建议）

```text
Phase6.2 完成
  → 真实跑 3–5 次日课
  → 观察：是否还迷路？是否还想点图谱/深挖？是否知道下一步？
  → 再决定是否开 P0-3 入口降噪
```

P0-3 可能因 6.1+6.2 自然降优先级。继续沿：**可信入口 → 可信验证 → 可信回流**。
