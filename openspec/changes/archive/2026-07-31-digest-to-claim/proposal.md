# digest-to-claim

## Why

早晚推送与「有用」兴趣写回已有，但有用之后没有进入「可考 → 过门」链路，外部输入停在动态流，假懂问题没被碰到。

对应 `docs/PRODUCT.md` 演进 §5：外部输入最终要过关。

## What changes

| 块 | 内容 |
|----|------|
| A | 从 `interest` / 有用 shell 事件晋升为 claim 候选（用户确认或一键） |
| B | Compass（或既有抽主张路径）生成 1–3 条可检验 claim；拒空话 |
| C | 晋升后进今日计划或轻队列；可开考；同一 gate |
| D | Settings「动态」CTA + REST/MCP；不自动刷屏 |

## Out

- 自动把所有资讯变成 claim（必须用户「有用」或显式晋升）
- 新建泛资讯阅读器 / 播客产品
- 改间隔公式或 Critic
- 把主能力只做在渠道侧

## Acceptance

对一条已标有用的动态，用户可一键生成可考 claim 并进入计划/欠练；空话被拒或需改写；开考走现有 examine finalize。

## Agent owns / do not touch

- **Owns:** `db/ops` shell/interest/note/claim 晋升、抽主张调用、Settings 动态 UI、相关 API/MCP、测
- **Do not touch:** Chat 结构块原语、Bootcamp 步进、`close_day`、`depends_on` 图式、面试简报
