# Tasks — topic-session-quiz

## 后端

- [x] 1. `core/models.py`：加 `TopicExamineVerdict` DTO（current_claim_id/done/verdict/follow_up/session_done）
- [x] 2. `core/agents/axiom.py`：加 `run_topic_examine(topic, claims, answer, history)` —— Axiom 主题穿梭，返回 `TopicExamineVerdict`；stub bypass
- [x] 3. `prompts/axiom.md`：加主题穿梭指令段（多 claim 自主流转 + verdict 带 current_claim_id）
- [x] 4. `api/routes.py`：`/v1/examine` 支持 `topic` 模式（传 topic + answer + history），`done=true` 时 `apply_examine_verdict(current_claim_id, verdict)`；保留 `claim_id` 旧模式
- [x] 5. `mcp/server.py`：`gotit_examine` 加 `topic` 参数支持主题模式
- [x] 6. `db/ops.py`：加 `list_topic_claims_today(topic)` —— 取今日 plan items 里该 topic 未 mastered 的 claims

## 前端

- [x] 7. `web/src/App.tsx`：考我模式改主题 session 聊天式
  - 去掉题目 tab、跳过、提交回答、删除此题、删除确认 modal、topicFilter 相关逐题逻辑
  - 选中主题 chip → 进入主题对话 session（examineChat state）
  - 底部输入框 + 发送按钮（调 `/v1/examine` topic 模式）
  - `session_done=true` → 禁用输入
- [x] 8. `web/src/styles.css`：清理题目 tab/跳过/提交/删除相关样式（claim-tab/confirm-modal 等已移除）

## 测试 + gate

- [x] 9. `tests/test_e2e.py`：加主题模式 e2e（topic 模式首轮 + answer 后 verdict 切 claim + session_done）；旧 claim_id 模式回归
- [x] 10. `./scripts/gate.sh` 全绿 + npm build + 浏览器手测
- [x] 11. sync openspec + 归档 topic-session-quiz
