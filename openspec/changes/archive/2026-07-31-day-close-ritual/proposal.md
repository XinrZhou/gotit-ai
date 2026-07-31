# day-close-ritual

## Why

产品强在「今天欠什么、开练」，弱在「今天可以停了」。没有收工边界，搭子容易变成无限催练，长期不愿意打开。

对应 `docs/PRODUCT.md`：温度（催考有分寸）+ 演进 §4 今日收工。

## What changes

| 块 | 内容 |
|----|------|
| A | 确定性「可收工」条件（欠清 / 今日计划验证项完成 / 用户主动收工）+ `day_close` 记录 |
| B | companion 白名单工具 `close_day`；空态/简报「收工」CTA |
| C | 短复盘素材（过了几道、还挂哪）可供晚间 digest 复用；不自动刷屏推送 |
| D | REST + MCP 镜像；文案克制、可跳过 |

## Out

- LLM 决定「你今天够了」作为唯一条件（可作文案，条件须代码可测）
- 改掌握门 / 间隔公式 / Critic
- 自动开下一轮考试
- 游戏化打卡排行

## Acceptance

用户可主动收工；欠清时空态出现温和收工入口；收工后当日不再强推开考 CTA（仍可手动开练）；有可测的 close 记录与复盘摘要字段。

## Agent owns / do not touch

- **Owns:** `db/ops/day.py`（close 相关）、可选 alembic、`api/routes` day、`mcp` close 工具、`companion_tools.close_day`、SessionStart / 今日简报收工 CTA、相关测
- **Do not touch:** `ChatMessage` 结构化块原语（归 `chat-action-blocks`）、digest→claim 晋升、`interview_ramp`、`core/schedule.py` 公式
