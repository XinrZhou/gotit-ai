# companion-tool-trail

## Why

Companion 白名单工具已会调、结果已进 `metadata.tool_calls`，但聊天里**看不见**轨迹，也无法一键跟进 `start_examine` 的开考准备——搭子「办了事」仍要用户自己点顶栏「考我」。

对应 `docs/PRODUCT.md` 演进 §1（搭子更能办事）与 OpenSpec Next candidate：
「UI for `metadata.tool_calls` / one-tap follow `start_examine`」。

## What changes

| 块 | 内容 |
|----|------|
| A | `start_examine` 成功时把精简 `open_examine` 载荷挂上对应 `tool_calls[]` 项（不只给 LLM） |
| B | Chat 气泡下安静 tool trail（chip + 悬停摘要） |
| C | 有可开考载荷时一键「开考」→ 复用现有 `startWorkflow` + examine 路径 |

## Out

- 挂上完整 gotit MCP 目录 / 全员多模型  
- Interview countdown ramp（P4）  
- Axiom harness holdout UI  
- 改 Critic / gate / 排程公式  

## Acceptance

有工具调用的 agent 气泡下能看到安静轨迹；若调用了成功的 `start_examine`，一点「开考」即进入考我会话（claim 或 note）——门仍走 `/v1/examine`。
