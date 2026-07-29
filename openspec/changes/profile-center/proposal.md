# profile-center — 设置（通用 / 技能 / 连接器）

## Why

搭子已能按需注入 Skill，但缺少统一设置面：用户无法安装自己的 Skill、
也无法给 companion agent 挂外接 MCP。参考 QoderWork 的「已安装 + 自己配置」
思路（无市场），让技能与连接器直接供 gotit 内几个 agent 消费。

## Scope

### In

- 设置壳：三栏 — **通用** / **技能** / **连接器**（侧栏齿轮入口）
- 通用：简历导入/查看入口（复用现有 modal）
- 技能：内置 + 用户安装列表；开/关；上传 `SKILL.md` / `.md` 安装（无市场）
- 连接器：MCP 已安装列表；粘贴 JSON 或手动填（stdio / http / sse）；开/关；探测状态
- Chat：仅展示 **enabled** 技能；发消息时把 enabled 连接器挂为 agent toolsets
- REST ↔ MCP 对等工具；alembic `0006`

### Out

- Skill / MCP 市场或广场
- OpenClaw 宿主侧配置编辑
- 多用户 / OAuth；`.env` / LLM key 编辑
- Agent rubric 热编辑

## Verification

- `uv run pytest`（skills / connectors / chat）
- `cd web && npm run build`
- 手动：打开设置 → 装 skill → 托盘可见；加 MCP → 开开关 → 有 LLM 时 agent 可调 tool
