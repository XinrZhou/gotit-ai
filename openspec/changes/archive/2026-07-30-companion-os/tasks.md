# companion-os — tasks

## P0 — 通道打通

- [x] 本机安装 OpenClaw 2026.7.1-2（Node 22）+ `@tencent-weixin/openclaw-weixin`（enabled）
- [x] 扫码登录微信：`openclaw channels login --channel openclaw-weixin`
- [x] 配置 gotit MCP（stdio）；`openclaw mcp doctor gotit --probe` → ok
- [x] 微信私聊调通 `gotit_health`（返回 0.1.0）；模型 zai/glm-5.1 + gateway 已起
- [x] 文档：`docs/openclaw-wechat.md` + `skills/gotit/SKILL.md` WeChat 节
- [x] （可选）微信再验 `gotit_today` / IDENTITY — 跳过；通道已验收 health

## P1 — 早晚简报（初版，已由 P1c 取代语义）

- [x] OpenClaw cron：早推科技/金融摘要（来源可配置 RSS）
  - `skills/digest/` + `docs/openclaw-digest.md`；`install-cron.sh` 注册 `gotit-morning-digest`（默认 08:00 Asia/Shanghai）
- [x] 晚推：摘要回顾 + `gotit_today` 待检摘录（1～3 条）← **P1c 起废弃混推**

## P1b — 外设写回（原 openclaw-bridge）

- [x] `db.ops.shell`：record_shell_event / record_interest / list_shell_activity / profile_v0 / graph_v0
- [x] core models：Shell* / ProfileView / GraphView
- [x] REST routes + MCP tools（对等）
- [x] digest：写回 shell_event + tip 含 event_id；SKILL「有用」→ interest
- [x] Web Settings「动态」只读观测（activity + 概览；图谱 UI 另定）
- [x] pytest (`tests/test_shell_bridge.py`)
- [x] docs：SYSTEM / openclaw-digest / gotit SKILL

## P1c — digest-v2（计划触达 + 资讯分离）

- [x] `DigestPrefs` + `db.ops.shell` get/put；REST `/v1/shell/digest-prefs` + MCP 对等
- [x] `fetch_digest.py`：`morning`（当日 plan）/ `evening`（明日询问）/ `news`（仅 RSS）；晚报**不再**附今日待检
- [x] 默认 AI 源（量子位 / HF / OpenAI / DeepMind 等）；支持 YouTube `channel_id` Atom；关键词过滤
- [x] `install-cron.sh`：早/晚计划 job；可选独立 news job（默认关）
- [x] Web Settings「计划推送」：源 / 时间 / 开关 / 关键词；「保存并同步」→ OpenClaw cron
- [x] docs：openclaw-digest / SYSTEM / README；pytest prefs + digest 格式

## P1d — Apple 计划桥

- [x] OpenSpec：本段 + design 写入策略（同日同标题 **skip**；`source=manual`）
- [x] `skills/apple-plan/`：`parse.py`（Notes/合并纯逻辑）+ JXA fetch + `import_plan.py`
  - `import reminders --list "学习计划" [--from/--to]`；`import notes`（标题/文件夹/`--file`）
  - 默认 dry-run；`--apply` 写 `gotit_upsert_plan_item`（REST 或 db.ops）
- [x] docs：`docs/openclaw-apple-plan.md`（安装、权限、格式、与 P1c 关系）
- [x] pytest：Notes 解析 + skip 合并（真机 osascript → 手动验收）
- [x] Settings「资料」：导入说明（不读 Apple）；SYSTEM / README 同步
- [x] 不在 `src/gotit` 调 Apple
- [x] 删除：MCP `gotit_delete_plan_item` + Reminders sync
- [x] `plan_items.due_time`；upsert/delete 自动 Apple sync；早推 import→push reconcile；空计划不写动态

## P2 — 微信指挥 coding

- [x] coding skill：绑定 1～N 个 workspace allowlist（`skills/coding/`）
- [x] 完成回微信摘要；失败回错误要点（SKILL 约定）
- [x] （可选）`gotit_add_memory` 记 lesson（SKILL 约定）

## P3d — 面试信息（gotit）

- [x] ORM + domain model：`InterviewEvent`
- [x] `db.ops`（`interview.py`）+ barrel 导出
- [x] REST：`/v1/interviews` CRUD + due-reminders
- [x] MCP：对等工具；更新 `skills/gotit/SKILL.md`
- [x] pytest：录入 / 状态变更 / due 窗口去重
- [x] Web：Settings「资料」面试安排面板

## P3a / P3b / P3c — 触达闭环

- [x] one-thing：早推首条 `⭐ 优先`（已在 `format_morning_plan`）
- [x] failure-digest：examine 非 passed → `failure_digest` memory + skill 投递；同 claim 同结局去重
- [x] voice-teach：微信语音 → 转写（OpenClaw）→ `gotit_teach`（`skills/voice-teach/`）

## P3d 提醒投递

- [x] OpenClaw skill：`skills/interview-remind/` 调 due-reminders → 微信；成功后 `mark_interview_reminded`
- [x] 默认 D-1 与开赛前 2h（`remind_offsets_hours=[-24,-2]`）

## P4 — 后置（本 change 不勾选）

- [ ] 面试倒计时升温模式（另开 change）

## Gate

- [x] `uv run pytest`（interview + failure_digest + digest + 相关）
- [x] 文档 / SYSTEM / README 同步；OpenClaw 软链与 cron 写在各 skill
- [x] 手动清单：微信通道已在 P0 验收；挂题/面试提醒/coding 需本机软链 skill 后人工点一次
