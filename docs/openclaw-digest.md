# OpenClaw 早晚简报（companion-os P1）

gotit **不**抓新闻、不跑 cron。编排在 OpenClaw；晚报待检来自 MCP/同源 `gotit_today`。

相关：[`docs/openclaw-wechat.md`](openclaw-wechat.md)（P0 微信通道）、仓库 `skills/digest/`。

## 本机进度

P1 落地物：

| 路径 | 作用 |
|------|------|
| `skills/digest/SKILL.md` | OpenClaw skill 说明 |
| `skills/digest/config.json` | RSS / 条数 / 建议 cron / 时区 |
| `skills/digest/fetch_digest.py` | 确定性抓取 + 格式化（早/晚） |
| `skills/digest/install-cron.sh` | 软链 skill + 注册两条 cron |

默认时区 **Asia/Shanghai**；早 `0 8 * * *`、晚 `0 21 * * *`（可改 config）。

## 1. 软链 skill

```bash
source ~/.nvm/nvm.sh && nvm use 22
ln -sfn /Users/zxr/workspace2026/gotit-ai/skills/digest \
  ~/.openclaw/workspace/skills/digest
```

（路径按本机仓库改。）

## 2. 改 RSS / 时间

编辑 `skills/digest/config.json`：

- `feeds[]` — `id` / `label` / `url`（默认 4 个：Solidot、36氪、少数派、The Verge）
- `item_count` — 默认 5
- `morning_cron` / `evening_cron` — 5 段 cron
- `timezone` — 默认 `Asia/Shanghai`
- `gotit.api_url` — 空则 `uv`+DB 读 today；可填 `http://127.0.0.1:8787` 走 REST（需环境变量 `GOTIT_API_KEY`）

单源失败会在正文末尾列出，**不会**整任务静默空失败。

## 3. 本地试跑脚本（不经微信）

```bash
cd /Users/zxr/workspace2026/gotit-ai
uv run python skills/digest/fetch_digest.py morning
uv run python skills/digest/fetch_digest.py evening
```

晚报应含 `【今日待检】`；无计划时为 **「今日无待检。」**

## 4. 注册 cron → 微信

Gateway 需在跑；微信已按 P0 登录。投递目标从最近一次 `openclaw-weixin` 私聊 session 解析（也可手动 `WEIXIN_TO=...`）。

```bash
cd /Users/zxr/workspace2026/gotit-ai
chmod +x skills/digest/install-cron.sh
./skills/digest/install-cron.sh
```

手动触发验收：

```bash
openclaw cron list
openclaw cron run <morning-job-id> --wait --wait-timeout 3m
openclaw cron run <evening-job-id> --wait --wait-timeout 3m
openclaw cron runs --id <job-id> --limit 5
```

改时间后：改 `config.json` 再跑一次 `install-cron.sh`（会删同名旧 job 再加）。

或手工：

```bash
openclaw cron edit <job-id> --cron "30 7 * * *" --tz Asia/Shanghai
```

## 写回 gotit（观测真源）

`fetch_digest.py` 默认在推送正文生成后调用 `record_shell_event`
（db 直写，或 `gotit.api_url` → `POST /v1/shell/events`）。文末带：

```text
event_id=<uuid>
```

用户回「这篇有用 N」时，OpenClaw 调 `gotit_record_interest`（或
`POST /v1/shell/interest`），关联该 `event_id`。**不做**自动 ingest。

Web：设置 → **外设** 查看 activity / 画像 v0 / 图谱 v0。
API：`GET /v1/shell/activity`、`/v1/obs/profile`、`/v1/obs/graph`。

详见 OpenSpec `openspec/changes/companion-os/`（P1b 外设写回）。

## 6. 验收清单

- [x] `fetch_digest.py morning` 有约 5 条或明确降级提示（本机已验）
- [x] `fetch_digest.py evening` 含今日待检或「今日无待检」（本机已验）
- [x] `openclaw cron run` 早/晚各一次，微信 `delivered: true`（2026-07-29）
- [x] 时区 Asia/Shanghai；RSS/时间可改（`config.json` + `install-cron.sh`）
- [x] 微信 MCP `gotit` doctor probe 仍 ok（P0 未破坏）

## 边界

- 勿在 `src/gotit/` 增加微信 SDK
- coding 遥控 / 面试提醒 → P2 / P3d，不在本页
