# companion-os — tasks

## P0 — 通道打通

- [x] 本机安装 OpenClaw 2026.7.1-2（Node 22）+ `@tencent-weixin/openclaw-weixin`（enabled）
- [x] 扫码登录微信：`openclaw channels login --channel openclaw-weixin`
- [x] 配置 gotit MCP（stdio）；`openclaw mcp doctor gotit --probe` → ok
- [x] 微信私聊调通 `gotit_health`（返回 0.1.0）；模型 zai/glm-5.1 + gateway 已起
- [x] 文档：`docs/openclaw-wechat.md` + `skills/gotit/SKILL.md` WeChat 节
- [ ] （可选）微信再验一次 `gotit_today`；填写 `IDENTITY.md` / `USER.md` 人设

## P1 — 早晚简报

- [x] OpenClaw cron：早推科技/金融摘要（来源可配置 RSS）
  - `skills/digest/` + `docs/openclaw-digest.md`；`install-cron.sh` 注册 `gotit-morning-digest`（默认 08:00 Asia/Shanghai）
- [x] 晚推：摘要回顾 + `gotit_today` 待检摘录（1～3 条）
  - `fetch_digest.py evening`；空计划文案「今日无待检。」；cron `gotit-evening-digest`（默认 21:00）

## P1b — 外设写回（原 openclaw-bridge）

- [x] `db.ops.shell`：record_shell_event / record_interest / list_shell_activity / profile_v0 / graph_v0
- [x] core models：Shell* / ProfileView / GraphView
- [x] REST routes + MCP tools（对等）
- [x] digest：写回 shell_event + tip 含 event_id；SKILL「有用」→ interest
- [x] Web Settings「动态」只读观测（activity + 概览；图谱 UI 另定）
- [x] pytest (`tests/test_shell_bridge.py`)
- [x] docs：SYSTEM / openclaw-digest / gotit SKILL

## P2 — 微信指挥 coding

- [ ] coding skill：绑定 1～N 个 workspace allowlist
- [ ] 完成回微信摘要；失败回错误要点
- [ ] （可选）`gotit_add_memory` 记 lesson

## P3d — 面试信息（gotit）

- [ ] ORM + domain model：`InterviewEvent`
- [ ] `db.ops`（建议 `interview.py`）+ barrel 导出
- [ ] REST：`/v1/interviews` CRUD + due-reminders
- [ ] MCP：对等工具；更新 `skills/gotit/SKILL.md`
- [ ] pytest：录入 / 状态变更 / due 窗口去重
- [ ] Web：最小列表 + 新建/编辑（可与 Drill 页同区）

## P3a / P3b / P3c — 触达闭环

- [ ] one-thing：早 cron 只推 1 条最高优先级 claim
- [ ] failure-digest：examine 非 passed → 微信短讯（缺口 + 再检提示）；同 claim 同结局不重复
- [ ] voice-teach：微信语音 → 转写 → `gotit_teach` → 回结果

## P3d 提醒投递

- [ ] OpenClaw cron：调 due-reminders → 微信；成功后写 `last_reminded_at`
- [ ] 默认 D-1 与开赛前 2h（可用 offsets 配置）

## P4 — 后置（本 change 不勾选）

- [ ] 面试倒计时升温模式（另开 change）

## Gate

- [ ] `uv run pytest`（interview + shell + 相关）
- [ ] `./scripts/gate.sh` 或约定子集
- [ ] 手动清单：微信 today / 早一件事 / 挂题短讯 / 面试提醒 / 动态观测各跑通一次
