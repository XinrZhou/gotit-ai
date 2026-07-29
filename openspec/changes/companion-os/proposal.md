# companion-os — 微信搭子外壳 + 学习闭环触达 + 外设写回

## Why

gotit 已是学习验证心脏（Chat / 日计划 / examine·teach·drill），但触达弱：
用户人在外面时进不来，资讯与 coding 也不该塞进 gotit 内核。需要一层
**OpenClaw 外壳**（微信入口 + 定时推送 + 本机 coding），并把几条高价值闭环
焊回验证脊梁；同时补上「面试日程」领域数据，以及统一的**外设事件写回**
（观测 → 画像 → 图谱），避免 OpenClaw 日志成为真相。

## Scope

### In（按优先级）

| # | 能力 | 落点 |
|---|------|------|
| P0 | 微信频道接入 OpenClaw + 挂载现有 gotit MCP | OpenClaw |
| P1 | 早晚简报（科技/金融等）+ 晚间挂「今日待检」 | OpenClaw cron + gotit MCP |
| P1b | **外设写回**：`shell_event` / `interest`；digest 写回；观测 / 画像 v0 / 图谱 v0 | **gotit** + digest skill |
| P2 | 微信指挥本机 coding（改仓 / 跑测 / 回消息） | OpenClaw agent |
| P3a | **今日只做一件事**：早推队列最高优先级 1 条 | OpenClaw + `gotit_today` |
| P3b | **失败复盘短讯**：examine 非 passed → 缺口摘要 + 预约再检 | gotit 写事件 / OpenClaw 投递 |
| P3c | **通勤语音回讲**：微信语音 → Echo teach → 写回队列 | OpenClaw + gotit MCP |
| P3d | **面试信息录入 + 提醒**（公司/岗位/时间/轮次/备注） | **gotit 新域** + OpenClaw cron 提醒 |
| P4（后置） | 面试倒计时升温模式（依赖 P3d 日程） | 后置 change |

### Out

- 在 gotit 内做微信 / 飞书频道适配器
- 完整「面试倒计时升温」（本变更只建日程与提醒骨架）
- 每条 RSS 自动 ingest / 完整图数据库 / 向量库
- 多用户 / OAuth；第二大脑式新闻收藏堆

## Verification

- gotit：interview 域 + shell/obs REST/MCP 对等 + pytest；gate 相关子集绿
- OpenClaw：微信私聊可调 `gotit_today`；cron 早晚可投递；digest tip 含 event_id
- Web：设置「外设」能看到动态
- 手动：录入一场面试 → D-1 / 当日提醒；今日一件事早推；挂题后收到复盘短讯
