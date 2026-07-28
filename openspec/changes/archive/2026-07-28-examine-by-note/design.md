# Design — examine-by-note

## session 维度

```
旧：主题 chip（claim.topic 聚合）→ 选主题 → session
新：今日笔记列表 → 选笔记 → session（章鱼哥穿梭该笔记的 claims）
```

## 后端

### /v1/examine 三模式

- `note_id` 模式（新，主用）：传 note_id，`list_note_claims(note_id)` 取该笔记未 mastered claims，穿梭
- `topic` 模式（保留）：传 topic，`list_topic_claims_today(topic)`
- `claim_id` 模式（保留）：单题多轮

判定优先级：note_id > topic > claim_id。

### list_note_claims(note_id)

```python
select(ClaimRow).where(
    ClaimRow.source_note_id == note_id,
    ClaimRow.user_id == user_id,
    ClaimRow.status != MASTERED,
).order_by(ClaimRow.created_at)
```

不限今日（笔记的 claims 都属于该笔记，旧笔记也能考）。按 created_at 排序。

### 复用

`run_topic_examine` / `stub_topic_examine` 已是「claims 列表穿梭」逻辑，与主题无关，直接复用，传 claims 即可。`TopicExamineVerdict` 结构通用（current_claim_id/done/verdict/follow_up/session_done），不改名。

## 前端

### ExaminePage

- 顶部：今日笔记入口列表（横向 chip 或纵向列表）。每条显示 `笔记标题 · N 题`（N = note.claim_ids.length）。N=0 的不显示入口。
- 选中一条 → onExamineStart(note) → 调 `/v1/examine {note_id}` → 章鱼哥开场
- 对话区：ChatLog + Composer（不变）
- session 进行中：顶部高亮选中笔记，可点其他笔记切换 session（切换 = 重置 chat）
- session_done：禁用输入

### store

- `examineTopic: string | null` → `examineNote: DayNote | null`
- `onExamineStart(note: DayNote)` → POST `/v1/examine {note_id: note.id}`
- `onExamineAnswer` → POST `/v1/examine {note_id, answer, history}`
- 删除 `onFillQueue`（前端按钮已去）

### Shell

- examine mode 的 head-actions 删除「补回顾」按钮

## Risks

- 笔记 claim_ids 含已 mastered 的，N 偏高 → 可接受（显示"抽过几题"），实际穿梭只考未 mastered
- 旧笔记也能考（不限今日）→ 符合"按笔记复习"预期
