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
Web 设置「动态」：人话展示早/晚简报与兴趣写回 + 概览计数（图谱 UI 暂未挂）。

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

1. **digest（P1c）** — `morning`=当日 plan；`evening`=明日 plan 询问；`news`=独立 AI/YouTube RSS；写回 shell_event。**禁止**资讯与待检/计划混在一条
2. **apple-plan（P1d）** — Mac Reminders/Notes → `gotit_upsert_plan_item`；不进 gotit 内核
3. **failure-digest** — examine 非 passed → 微信短讯
4. **voice-teach** — 语音转写 → `gotit_teach`
5. **coding** — 绑定 workspace；可选 `gotit_add_memory`
6. **interview-remind** — cron 调 due-reminders → 微信

## P1c digest-v2

| Job | 默认时间 | 正文 |
|-----|----------|------|
| morning | 08:00 | 当日开放 plan items（首条标优先）；默认**不含**资讯 |
| evening | 21:00 | 明日 plan：有 → 问是否调整；无 → 问是否新建；**不含**今日待检、**不含**资讯 |
| news（可选） | 关 / 用户开 | 仅 RSS（量子位/实验室博客/可选 YouTube Atom） |

Prefs 真源：gotit `digest_prefs`（REST/MCP）；`skills/digest/config.json` 为文件默认 + cron 回退。Settings「计划推送」读写 prefs；改 cron 后点「保存并同步」（`POST /v1/shell/digest-cron/sync` → `install-cron.sh`）。

## P1d Apple 计划桥

落点：**仅** `skills/apple-plan/`（OpenClaw skill + 本机脚本）。**禁止**
`src/gotit/` import AppleScript / EventKit / 读 NoteStore.sqlite。

```text
Mac Reminders / Notes
        │  osascript (JXA) — Automation / Reminders TCC
        ▼
skills/apple-plan/import_plan.py
        │  REST 或 db.ops（与 MCP 同源）
        ▼
gotit plan_items（日计划真源）
        │
        └─ P1c digest cron 只读 gotit plan（B 不改推送文案）
```

### 约定

| 源 | 映射 |
|----|------|
| Reminders | 指定列表（默认「学习计划」）；`dueDate` → gotit `day`；无 due → **显式跳过并计入 warnings**（全无 due 则失败） |
| Notes | 文件夹或标题含「学习计划」；正文须含 `## YYYY-MM-DD` + `-`/`- [ ]` 清单；非法行/无日期块 → **硬错误，不静默丢** |

### 写入策略（v0 写死）

- **gotit 是真源**；Apple 只是入口。不做双向实时同步。
- 默认同日 **标题 casefold 去重：已存在 → skip**（不改 status / claim_id，避免踩 examine 队列）。
- `source = manual`（不新增枚举；非 `queue`）。
- 默认 **dry-run** 打印 `day / title / create|skip`；`--apply` 才写入。
- 可重复单向再导入；skip 保证幂等。
- **删除**：MCP `gotit_delete_plan_item`（`item_id` 或 `day`+`title`）；`import_plan.py rm` 同时清 Reminders（按标题 + 可选到期日）。
- 可选：导入成功后 stdout 摘要条数，供 OpenClaw 短回微信（不在 gotit 内投递）。

### 权限

Reminders / Automation（Notes）TCC；**不要求** Full Disk Access。首次授权人工点允许。详见 `docs/openclaw-apple-plan.md`。

## P3 闭环语义

| 能力 | 触发 | 写回 gotit？ |
|------|------|----------------|
| 当日 / 明日计划推送 | 早/晚 cron（P1c） | shell_event；改计划靠用户回复→MCP |
| 失败复盘 | examine 非 passed | memory lesson；短讯是触达 |
| 语音回讲 | 用户发语音 | teach session + verdict |
| 面试提醒 | cron | 更新 `last_reminded_at` |
| 资讯 / 有用 | news cron / 用户回复 | shell_event / interest |
| Apple 导入 | 手动或 skill | plan_items |

## P4 后置（倒计时升温）

有 `InterviewEvent` 后按 `scheduled_at - now` 分档调强度。**本变更不实现**。

## Risks

- 微信插件版本与 OpenClaw 版本绑定；仅私聊
- 本机需常开 + 防休眠；coding 权限需 workspace allowlist
- 失败复盘若轮询过频会吵 → 每 claim 每结局至多一条
- shell_event 增长 → 后续可 prune 或迁独立表；写回失败应在 tip 暴露
