# OpenClaw 计划触达 + 可选资讯（companion-os P1c）

gotit **不**抓新闻、不跑 cron。编排在 OpenClaw。

| Job | 默认 | 正文 |
|-----|------|------|
| `morning` | 08:00 | **今日计划**（仅计划；不同资讯） |
| `evening` | 21:00 | **明日计划**询问（有→调整；无→新建）。**不含**今日待检、**不含**资讯 |
| `news` | 默认关 | 仅 AI/YouTube RSS |

有计划时早/晚推送会顺带 `apple-plan push` 到提醒事项「学习计划」。

相关：[`docs/openclaw-wechat.md`](openclaw-wechat.md)、`skills/digest/`。Apple 导入见 P1d（另一 agent）。

## 本机进度

| 路径 | 作用 |
|------|------|
| `skills/digest/SKILL.md` | OpenClaw skill |
| `skills/digest/config.json` | 文件默认（prefs 回退） |
| `skills/digest/fetch_digest.py` | morning / evening / news |
| `skills/digest/install-cron.sh` | 注册 cron（读 gotit prefs） |
| Settings「计划推送」 | `GET/PUT /v1/shell/digest-prefs`；「保存并同步」→ `POST /v1/shell/digest-cron/sync` |

时区默认 **Asia/Shanghai**。

## 1. 软链 skill

```bash
source ~/.nvm/nvm.sh && nvm use 22
ln -sfn /Users/zxr/workspace2026/gotit-ai/skills/digest \
  ~/.openclaw/workspace/skills/digest
```

## 2. 配置源 / 时间

**推荐**：Web 设置 → **计划推送**（写入 gotit `digest_prefs`）。改 cron 后点 **「保存并同步」**。

也可编辑 `skills/digest/config.json`（API 不可达时回退）：

- `feeds[]` — AI 站 / YouTube Atom（`…/feeds/videos.xml?channel_id=UC…`）
- `keywords` — 标题过滤
- `news_enabled` / `news_cron` — 独立资讯 job（与早/晚计划分离；早推不再附资讯）

默认源：量子位、HF Blog、OpenAI News、DeepMind（MarkTechPost 默认关）。

## 3. 本地试跑

```bash
cd /Users/zxr/workspace2026/gotit-ai
uv run python skills/digest/fetch_digest.py morning --no-remote-prefs
uv run python skills/digest/fetch_digest.py evening
uv run python skills/digest/fetch_digest.py news --no-writeback
```

晚报**不应**出现「今日待检」或 RSS 列表。

## 4. 注册 cron

优先：Settings「计划推送」→ **保存并同步**（或 `POST /v1/shell/digest-cron/sync`）。

也可手动：

```bash
./skills/digest/install-cron.sh
```

改 prefs 后需再跑一次以刷新 cron 表达式。

## 写回

`shell_event` + 文末 `event_id=`。资讯「这篇有用 N」→ `gotit_record_interest`。计划回复 → `gotit_upsert_plan_item`。

## 边界

- 勿在 `src/gotit/` 增加微信 SDK
- 资讯与计划**不得**混在同一条晚报
- Apple 计划导入 → [`docs/openclaw-apple-plan.md`](openclaw-apple-plan.md)（P1d，不改本脚本推送主逻辑）
- coding / 面试提醒 → companion-os 其他段落
