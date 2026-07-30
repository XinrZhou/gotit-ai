# Proposal — digest evening wrap (今日复盘) + news 默认独立开

## Why

晚推标题是「晚报」，但 P1c 正文只问**明日计划**。明日为空时整条只剩 CTA，
看起来像「晚报没内容」；用户补计划后只会收到确认，仍没有当日复盘。

资讯需要推，但不能并入早/晚报。

## What

- `evening` = **今日计划复盘**（完成 / 未完成）+ **明日计划**询问
- 仍禁止混入 RSS / 「今日待检」claim 列表
- 空明日仍可推送（有今日复盘就不算空壳）；两边都空才可跳过动态写回
- `news_enabled` 默认 **开**，独立 `news_cron`（默认 20:00）；`morning/evening_include_news` 恒 false

## Out

- 不恢复晚报附带 due_claims / 资讯
- 不在 `gotit.core` 加微信逻辑
