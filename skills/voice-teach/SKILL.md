---
name: voice-teach
description: >-
  WeChat voice → transcript → gotit_teach (Echo). Reply with gaps / next_question
  or done summary. Transcription is OpenClaw/channel-side; gotit only runs teach.
---

# voice-teach — 通勤语音回讲（OpenClaw）

## 流程

1. 用户发微信**语音**（或「回讲：…」文字）
2. OpenClaw / 通道侧转写为文本（gotit **不**做 ASR）
3. 调 MCP：
   - 首轮：`gotit_teach(topic=…, answer=transcript, history=[])`
   - 续轮：带上上一轮返回的 history / next_question 上下文
4. 短回微信：`next_question` 或 `done` 时的 gaps / you_taught_well

## 话题

- 用户明示「回讲 XXX」→ `topic=XXX`
- 否则用今日计划首条开放项标题作 topic（`gotit_today`）
- 可选 `thread_id` 写入 companion 消息流

## 示例回复

```text
派大星听完了：还有缺口 —— 没讲清 QKV。
下一问：mask 在 decoder 里挡的是什么？
```

## 边界

- ASR / 语音文件不进 `src/gotit`
- 验证仍走 Echo + 既有 teach writeback；不自判 mastery
