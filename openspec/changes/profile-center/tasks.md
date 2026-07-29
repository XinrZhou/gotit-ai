# profile-center — tasks

## 1. Spec + models

- [x] OpenSpec proposal / design / tasks
- [x] `core.models`: SkillInfo, McpConnector
- [x] ORM + alembic `0006_profile_center`
- [x] `db.ops.skills` + `db.ops.connectors` + barrel

## 2. API + runtime

- [x] `api/routes/skills.py` + `connectors.py`；从 identities 迁出 skills GET
- [x] MCP tools 对等
- [x] `api/mcp_toolsets.py`：config → MCPToolset
- [x] `run_chat` 接受 `toolsets`；orchestrator 挂 enabled connectors
- [x] `load_skill` 支持用户 body（orchestrator 解析）

## 3. Web

- [x] SettingsPage：侧栏 资料 / Skills / MCP / 动态；Skill/MCP 查看编辑；动态人话列表
- [x] Shell 挂载；navRail 齿轮；`settingsOpen` in useShell
- [x] Chat tray 只列 enabled skills
- [x] types + api 调用

## 4. Verify

- [x] pytest：skills install/toggle、connectors CRUD/import
- [x] `cd web && npm run build`
- [x] 更新 `docs/SYSTEM.md`
