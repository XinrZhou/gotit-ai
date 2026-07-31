# interview-countdown-ramp

## Why

真实面试日程与 D-1 / T-2h 提醒已有（P3d），但临近面试时**不会略加强**项目深挖提示——日子里「面试和学习两张皮」仍缺一环。

对应 `docs/PRODUCT.md` §4：临近可略加强；永远可关；合并推送，禁止刷屏。  
companion-os 后置：**按 `scheduled_at - now` 分档调强度**。

## What changes

| 块 | 内容 |
|----|------|
| A | 确定性 `ramp_tier`（silent / light / warm / urgent）+ upcoming / due-nudge 视图 |
| B | `last_ramp_nudge_at` 去重 + prefs（enabled / 周上限） |
| C | REST + MCP + companion 只读 `get_upcoming_interview` |
| D | Settings 可关 + 列表分档提示；扩展 `interview-remind` 投递 ramp nudge |

## Out

- 自动改 plan / 自动开 drill / chat 内全自动 Sage  
- 增加 T-2h 以外的高频提醒  
- LLM 决定分档或掌握档位  
- 完整 MCP 挂进聊天  

## Acceptance

给定面试时间，分档可测且稳定；light/warm 可低频 nudge（可关、有去重）；对话里问「快面试了」时 companion 能读到 upcoming；D-1/T-2h 行为不变。
