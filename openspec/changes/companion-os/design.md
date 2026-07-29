# companion-os — design

## Architecture

```text
微信（个人号 ClawBot / iLink）
        │
   OpenClaw Gateway（本机常驻）
   ├─ channel: openclaw-weixin
   ├─ cron: morning digest / evening due / interview reminders / one-thing
   ├─ coding workspace skill（指定 repo）
   └─ MCP → gotit-mcp
              ├─ today / plan / examine / teach / memory（已有）
              ├─ shell_event / interest / obs profile+graph（P1b）
              └─ interviews CRUD + due reminders query（P3d）
```

**边界铁律（沿用 ADR-0001）：** 频道与推送投递在 OpenClaw；领域状态与验证逻辑在 gotit。

## P1b — 外设写回（原 openclaw-bridge）

```text
OpenClaw digest/cron/WeChat
        │  MCP/REST writeback
        ▼
gotit.db.ops.shell  →  memory_entries (kind=shell_event|interest)
        │
        ├─ list activity (obs)
        ├─ profile_v0 (aggregate trajectory + interest)
        └─ graph_v0 (claim ↔ topic ↔ project; optional interest→topic)
```

### Memory schema（v0 不新建表）

| kind | layer | content (JSON) | source |
|------|-------|----------------|--------|
| `shell_event` | working | `job`, `items[…]`, `due_summary`, `errors`, `delivery_ok` | `channel`, `skill`, `job`, `run_id` |
| `interest` | long | `event_id`, `item_index`, `title`, `link`, `feed_id` | `channel`, `skill` |

### API / MCP（对等）

| REST | MCP |
|------|-----|
| `POST /v1/shell/events` | `gotit_record_shell_event` |
| `POST /v1/shell/interest` | `gotit_record_interest` |
| `GET /v1/shell/activity` | `gotit_list_shell_activity` |
| `GET /v1/obs/profile` | `gotit_obs_profile` |
| `GET /v1/obs/graph` | `gotit_obs_graph` |

Digest 推送后 `record_shell_event`，tip 含 `event_id`；「这篇有用 N」→ `interest`。
Web 设置「外设」：activity + 精简 profile + graph 计数。

## gotit：面试信息（InterviewEvent）

现有 `resumes` / `drill_sessions` 只有「怎么练」，没有「哪天面谁」。新增轻量表：

| 字段 | 说明 |
|------|------|
| `company` | 公司 |
| `role_title` | 岗位 |
| `scheduled_at` | 面试时间（tz-aware） |
| `round` | tech_1…hr / other（与 drill 轮次对齐，可空） |
| `status` | scheduled / done / cancelled |
| `notes` | 备注（JD 链接、面试官、地点） |
| `remind_offsets_hours` | 默认 `[-24, -2]`（相对 scheduled_at） |
| `last_reminded_at` | 防重复 |

API / MCP（对等）：`list_interviews` / `upsert_interview` / `update_interview_status` /
`list_due_interview_reminders(now)`。提醒文案由 OpenClaw Skill 生成；gotit 只返回结构化 due 列表。

## OpenClaw Skills

1. **digest** — RSS/API → 摘要；晚间追加 `gotit_today`；写回 shell_event
2. **one-thing** — 今日 plan 最高优先级 1 条 claim
3. **failure-digest** — examine 非 passed → 微信短讯
4. **voice-teach** — 语音转写 → `gotit_teach`
5. **coding** — 绑定 workspace；可选 `gotit_add_memory`
6. **interview-remind** — cron 调 due-reminders → 微信

## P3 闭环语义

| 能力 | 触发 | 写回 gotit？ |
|------|------|----------------|
| 今日一件事 | 早 cron | 否（只读 plan） |
| 失败复盘 | examine 非 passed | memory lesson；短讯是触达 |
| 语音回讲 | 用户发语音 | teach session + verdict |
| 面试提醒 | cron | 更新 `last_reminded_at` |
| 简报 / 有用 | digest / 用户回复 | shell_event / interest |

## P4 后置（倒计时升温）

有 `InterviewEvent` 后按 `scheduled_at - now` 分档调强度。**本变更不实现**。

## Risks

- 微信插件版本与 OpenClaw 版本绑定；仅私聊
- 本机需常开 + 防休眠；coding 权限需 workspace allowlist
- 失败复盘若轮询过频会吵 → 每 claim 每结局至多一条
- shell_event 增长 → 后续可 prune 或迁独立表；写回失败应在 tip 暴露
