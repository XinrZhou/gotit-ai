# examine-by-note — 考我 session 改为按笔记维度

> **Status: proposed 2026-07-28**

## Why

考我 session 维度当前是「主题（claim.topic）」，但 topic 依赖 Compass 抽取，stub 模式下全是 null，聚出来只有一个无意义的「未分类 · N」chip，没有区分价值，用户看不懂。

更可靠的 session 维度是**笔记（资料）**：用户写一条笔记 = 学了一个主题（如「提示词工程」），整理成测验抽出几条 claim。考我时选这条笔记进入 session，章鱼哥围绕该笔记的 claims 考你。主题 = 笔记标题，天然存在、不依赖 LLM。一场 session = 一条笔记。

同时去掉「补回顾」按钮（社招准备阶段题都是新题，不需要间隔重复队列）。

## Scope

### In

- **后端**：
  - `/v1/examine` 支持 `note_id` 模式：传 note_id，后端取该笔记未 mastered 的 claims（`source_note_id == note_id`），章鱼哥穿梭
  - `db/ops.list_note_claims(note_id)` 新增
  - `gotit_examine` MCP 加 `note_id` 参数
  - 复用 `TopicExamineVerdict` / `run_topic_examine` / `stub_topic_examine`（已是 claims 列表穿梭，与主题无关）
- **前端**：
  - `ExaminePage`：去掉主题 chip，改为今日笔记入口列表（每条显示 `· N 题`，点进入 session）
  - session 对话区不变（ChatLog + Composer），session 标题 = 笔记标题
  - store：`examineTopic` → `examineNote`（DayNote | null），`onExamineStart(note)` 调 note_id
  - 去掉「补回顾」按钮（Shell head-actions）
- **测试**：e2e 加 note 模式（首轮开场 → 答题判定切下一 claim → session_done）

### Out

- 间隔重复队列保留后端能力（fill_today_from_queue 不删），只去前端按钮
- claim.topic 字段保留（Compass 后续会用），不再作为考我维度

## Non-goals

- 不改回讲 / 项目深挖
- 不改 verdict 三值映射

## Verification

- `./scripts/gate.sh` 全绿（含旧 claim_id 单题模式回归 + 新 note 模式）
- 考我页：列今日笔记，点一条进入 session，章鱼哥开场问该笔记第一个 claim，答题判定切下一 claim，全部判完 session_done
- 无「补回顾」按钮、无主题 chip、无「未分类」
