# Proposal: verify-return-loop

## Why

验证脊柱在数据层已闭合（Examine/Teach → Critic → gate → writeback → schedule / failure / trajectory）。  
Phase6.1 已让 DailyBrief 上的「欠」可信。

用户动线仍断在 **验证结束之后**：

```text
看到芯片「过了 / 还差点 / 欠着下次」+「这轮考完了」
  → Composer 消失
  → 无主动作说明「今天还欠什么 / 这次改变了什么 / 下一步」
  → 须自己点「← 搭子」才可能看见更新后的 Brief / 账清
```

后端闭环完成；**用户感知闭环未完成** → 日课「做完一关」的成就感与留存被打断。

Phase6 链：可信入口（6.1）→ 可信验证（已有）→ **可信回流（本夹）**。  
P0-3 入口降噪：**本夹完成后先真用 3–5 天再决定**，不默认开做。

## What changes

在 **不改 gate / schedule / mastery 规则** 的前提下：

1. 验证 `session_done` 后展示安静 **Done 条**：结果 + 已有解释信号 + 对未来的影响（排程/状态，来自 writeback）+ 明确下一步 CTA。
2. 主 CTA：**回今天**（退出工作流 → chat 空首页/Brief，已 `refresh` 的 owed 可见）。
3. 按档位次要动作：almost → 可「接着练」同 claim；owe_next / passed → 以回今天为主（不新开推荐）。
4. Examine 与 **claim-bound Teach** 对称（过门路径）；Drill 本夹不改（不过门）。

## Out

- 改 `deterministic_gate` / `core/schedule.py` / failure 写回规则 / Claim 模型
- 新 Agent、新模型、AI 成长报告、成就系统、新 DB 实体
- 新推荐系统 / 自动选题
- P0-3 顶栏/空态入口大降噪（观察后再开）
- Drill 接 finalize；改评分阈值

## Success

用户完成一次过门验证后，不靠猜就知道：

1. 这次结果是什么；  
2. 为何是这个档（已有 gate reason / 轨迹，非新 LLM 终审）；  
3. 对未来有何影响（`next_review_at` / schedule_reason / 是否仍今日欠）；  
4. 下一步点哪里（回今天 / 接着练）。

体感一句话：

> 我刚才做的验证，改变了我的成长路径。

## Impact

- 主要：`web` Examine/Teach done 态、`useExamine`/`useTeach` 保留 writeback 摘要、ChatPage `setMode("chat")` 回程
- 次要：前端类型补全已有 writeback 字段；`docs/SYSTEM.md` 一句
- API：优先 **零新 endpoint**（响应里已有 writeback / verify）；仅当缺字段再薄补，不改算法
- 无 Postgres migration
