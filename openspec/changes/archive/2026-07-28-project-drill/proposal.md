# Project drill — 项目深挖 + 人格化

## Why

gotit-ai 当前只按天组织（daily plan），缺少跨天的「项目/主题」维度来聚拢资料/考点/进度。同时 agent 缺少人格与温度，流程偏死板。本次在现有验证引擎之上加项目维度（社招时是简历项目，社招后可演进为工作主题，不框死），并给 4 个 agent 赋予海绵宝宝人格，让产品轻松愉快、有记忆连续性。

## Scope

- In：
  - 数据模型：`ProjectRow` + note/claim/plan_item 加 `project_id`（泛化，不绑社招）
  - ops：project CRUD + 项目下 claims/notes 列表 + 项目进度
  - Sage agent：项目深挖追问官（多轮，SageVerdict），激活原 post-M0 的 Sage
  - 4 个 agent 人格化：海绵宝宝角色（章鱼哥/海绵宝宝/派大星/桑迪）+ 温暖文案 + 记忆连续
  - REST + MCP：projects CRUD + `/v1/projects/{id}/drill` + notes 加 project_id
  - 前端：左栏项目切换器 + 右栏 segmented 第三档 [项目深挖] + 项目卡片/深挖对话 + 新建编辑 modal + agent 头像/称呼人格化
- Out：提示词实验室前端、skill 管理、知识体系八股树、算法手撕、系统设计场景题、进度总览仪表盘（M1.5+）

## Non-goals

- 不改现有验证回路逻辑（Axiom/Compass/Echo 判定/抽取/回讲算法不动，只加人格 prompt 与称呼）
- 不做 MCP client（gotit-ai 保持 MCP server 身份，外部集成由 OpenClaw 承担）

## Persona mapping

| 代号 | 角色 | 人格 |
|------|------|------|
| Axiom | 章鱼哥 | 傲娇挑剔但认真，嘴硬心软 |
| Compass | 海绵宝宝 | 热情好奇爱张罗 |
| Echo | 派大星 | 憨憨好朋友，耐心倾听 |
| Sage | 桑迪 | 科学家气质，爱钻研追问 |

## Delivery notes

- `Project` 泛化（社招项目 / 工作主题通用），不绑社招字段。
- `project_id` 全部 nullable，旧数据不破坏。
- Sage 沿用 axiom/echo 的 build 模式（Pydantic AI + 真 LLM / stub fallback）。
- 人格化通过 prompt 注入 + 前端称呼/头像，不改 agent 接口契约。
