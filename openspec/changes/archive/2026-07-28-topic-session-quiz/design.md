# Design — topic-session-quiz

## 范式

```
旧：选题目 tab → 提交回答 → 判定单 claim → 下一题（逐题操作）
新：选主题 chip → 进入主题 session → 章鱼哥自主穿梭多 claim 追问 → 聊天回答
```

## 后端

### 新 DTO

```python
class TopicExamineVerdict(BaseModel):
    current_claim_id: UUID | None     # 当前在问的 claim
    done: bool                        # 是否对 current_claim 给了 verdict
    verdict: Literal["passed","almost","owe_next"] | None = None
    follow_up: str                    # 下一问题或总结
    session_done: bool = False        # 该主题所有 claim 都判完
```

### /v1/examine 双模式

- `claim_id` 模式（旧，兼容）：传 `claim_id` + 可选 `answer`/`history`/`verdict(bypass)`，返回旧 `ExamineVerdict` + writeback
- `topic` 模式（新）：传 `topic` + 可选 `answer`/`history`，后端取该主题未 mastered 的 claim 列表，Axiom 自主穿梭，返回 `TopicExamineVerdict` + writeback

判定：`body.topic` 存在 → 主题模式；否则 `claim_id` 旧模式。

### 主题模式流程

```
1. POST /v1/examine {topic: "提示词工程"}
   → 后端取今日 plan items 里 topic=提示词工程 且 claim 未 mastered 的 claims
   → 给 Axiom：主题 + claim 列表[{id, text}] + history
   → Axiom 选第一个 claim，抛开场问题
   → 返回 {current_claim_id, done:false, follow_up, session_done:false}

2. POST /v1/examine {topic, answer, history}
   → Axiom 看 answer + history，决定：
     a) 继续追问当前 claim（done:false, follow_up=下一问）
     b) 对 current_claim 给 verdict（done:true, verdict, current_claim_id）→ 后端 apply_examine_verdict 回写
        然后自主切下一 claim（follow_up=下一claim 问题, session_done:false）
        或所有 claim 都判完（session_done:true, follow_up=总结）
   → 返回 TopicExamineVerdict
```

### Axiom prompt 调整（axiom.md 加段）

主题模式指令：拿到主题 + 多个 claim，自主挑题，每题追问 1-3 轮给 verdict，切下一题，全部判完设 session_done。verdict 时必须带 current_claim_id。

### stub bypass（无 LLM key）

主题模式 stub：首轮 → 问第一个 claim 的 stub 问题；有 answer → 对 current_claim 给 passed，切下一 claim 或 session_done。

## 前端

- 主题 chip 行保留（topic-grouped-quiz 已做）
- 选中主题 → 进入该主题对话 session（不再有题目 tab）
- 对话区：章鱼哥气泡 + 用户气泡（沿用 bubble-row）
- 底部：输入框 + 发送按钮（像回讲/项目深挖 composer）
- 去掉：题目 tab、跳过、提交回答、删除此题、删除确认 modal
- session_done=true：对话末尾加「本主题都过了 ✓」系统消息，禁用输入
- history 只在前端 state（M0）

## MCP

`gotit_examine` 加 `topic` 参数支持主题模式；`claim_id` 保留兼容。

## Risks

- **Axiom 多 claim 穿梭质量**：LLM 可能忘记当前 claim 或乱切。缓解：prompt 明确「每次只问一个 claim，verdict 必带 current_claim_id」；history 带当前 claim 标记
- **session history 不持久化**：刷新丢。M0 接受，后续加 session 表
- **旧测试回归**：claim_id 模式保留，e2e 不动
