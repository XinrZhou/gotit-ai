# profile-center — design

## IA

```text
设置（Shell 级宽 Modal；标题在侧栏）
├── 资料     头像/称呼 · 简历入口
├── Skills   已安装 · 开关 · 上传安装
├── MCP      已安装 · 开关 · JSON/手动添加 · 状态点
└── 动态     OpenClaw 写回 activity · 概览（图谱 UI 另定）
```

入口：ChatPage navRail 底部齿轮。无 react-router。

## Data

### `user_skills`

| col | note |
|-----|------|
| user_id, name | unique together |
| body | markdown body（用户安装必填；内置偏好行可空） |
| notes | 短说明 |
| enabled | default true |
| source | `builtin` \| `user` |

内置仍来自 `prompts/skills/*.md`。列表 = 磁盘内置 ∪ DB 用户技能，再用
DB 行覆盖 `enabled` / 用户 `body`。

### `mcp_connectors`

| col | note |
|-----|------|
| user_id, name | unique |
| transport | `stdio` \| `http` \| `sse` |
| config | JSON：stdio→`{command,args,env}`；http/sse→`{url,headers}` |
| enabled | bool |
| last_status | `unknown` \| `ok` \| `error` |
| last_error | optional |

## Runtime

- `core/skills`：保留磁盘 load；catalog 合并在 `db.ops.skills`
- `run_chat(..., toolsets=)`：Pydantic AI `MCPToolset`（api 层构建，避免 core 依赖 FastMCP 细节过多；runtime 已用 pydantic-ai）
- `chat_orchestrator`：加载 enabled connectors → toolsets → `async with` 进入后 `run_chat`
- 探测：`POST …/probe` 短连 list_tools，写回 status

## API

| method | path |
|--------|------|
| GET/POST | `/v1/skills`（GET→SkillInfo[]；POST install） |
| PATCH/DELETE | `/v1/skills/{name}` |
| GET/POST | `/v1/connectors` |
| PATCH/DELETE | `/v1/connectors/{id}` |
| POST | `/v1/connectors/{id}/probe` |
| POST | `/v1/connectors/import`（粘贴 mcpServers JSON） |

MCP tools mirror the same ops.

## Risks

- STDIO MCP 拉起慢 / 环境缺失 → status=error，不阻断聊天（toolset 构建失败则跳过并记 error）
- PromptedOutput + tools 在部分网关上不稳定 → 有 toolsets 时仍用现结构；失败路径保留 stub
