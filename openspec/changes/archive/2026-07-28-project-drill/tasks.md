# Tasks — Project drill + 人格化

- [x] 1. OpenSpec：proposal/design/tasks（本文件）
- [x] 2. 数据模型：ProjectRow + note/claim/plan_item 加 project_id + DTO（Project/ProjectProgress/SageVerdict）+ Alembic 0003
- [x] 3. ops：project CRUD + list_project_claims/notes + project_progress + add_note/ingest_note 接 project_id
- [x] 4. Sage agent：prompts/sage.md + core/agents/sage.py + run_sage
- [x] 5. 人格化：prompts/{axiom,compass,echo}.md 加人格段（章鱼哥/海绵宝宝/派大星）
- [x] 6. REST：projects CRUD + /v1/projects/{id}/progress + /v1/projects/{id}/drill + notes 加 project_id
- [x] 7. MCP：gotit_list/add/get/update_project + gotit_drill_project + gotit_project_progress
- [x] 8. 前端：项目切换器 + segmented 第三档[项目深挖] + 项目卡片/深挖对话 + 新建编辑 modal + agent 人格化头像称呼
- [x] 9. 测试 + gate：project ops/drill 测试 + ruff/mypy/pytest + npm build + gate ok

## Delivery notes

- `Project` 泛化（社招项目 / 工作主题通用），不绑社招字段；`project_id` 全部 nullable，旧数据不破坏。
- Sage 沿用 axiom/echo 的 build 模式（Pydantic AI + 真 LLM / stub fallback），多轮 `SageVerdict`（done/depth_reached/gaps/follow_up）。
- 人格化通过 prompt 注入 + 前端称呼/头像（章鱼哥「章」/海绵宝宝 / 派大星「派」/桑迪「桑」），不改 agent 接口契约。
- REST/MCP 完整对齐：`/v1/projects*` + `gotit_*_project` + `gotit_drill_project`。
- Alembic 0003：projects 表 + day_notes/claims/plan_items 加 project_id（nullable + index）。
- 开发库（gotit.db）因 create_all 提前建了空 projects 表导致迁移冲突，drop 空 projects 表后 upgrade head 成功；生产/干净库无此问题。
- gate.sh 全绿：ruff / mypy / pytest 7 passed / harness 4-4 pass / npm build ok。
