# Tasks — resume-driven drill

按顺序执行，每步可独立跑 gate。`[gate]` 标记的步骤需通过 `./scripts/gate.sh`（或对应子命令）。

## 1. 地基：依赖与目录

- [x] `pyproject.toml` 加 `pypdf>=4.0`、`python-docx>=1.1`，`uv sync --all-extras`
- [x] 建 `src/gotit/core/resume/` 目录骨架 + `__init__.py`
- [x] `.gitignore` 加 `uploads/`；建 `uploads/` 目录
- [x] [gate] `uv run ruff check . && uv run mypy src`

## 2. 数据模型 + 迁移

- [x] `core/models.py` 加 `ResumeBasics` / `ResumeProject` / `ResumeDocument` / `ResumeRecord` / `ResumeParseOutput` / `DrillMaterial` / `DrillRound` / `DrillSession`；扩展 `SageVerdict`（加 `round`）
- [x] `db/models.py` 加 `ResumeRow`（user_id UNIQUE）/ `DrillMaterialRow` / `DrillSessionRow`
- [x] `alembic/versions/0004_resume_drill.py`：建 `resumes` / `drill_materials` / `drill_sessions` 三表
- [x] [gate] `uv run mypy src && uv run alembic upgrade head`

## 3. 文本提取层

- [x] `core/resume/extract.py`：`extract_text(content: bytes, content_type: str) -> str`（pypdf / python-docx / 直读）
- [x] `core/resume/extract.py`：`ResumeExtractError`（空文本时抛）
- [x] `tests/test_resume.py`：extract 单测（以 `tests/fixtures/sample.txt` 为主，pdf/docx 可选）
- [x] [gate] `uv run pytest tests/test_resume.py`

## 4. 结构化解析层（Compass 扩展）

- [x] `prompts/resume.md`：ResumeParser system prompt（复用海绵宝宝人格段 + 简历抽取契约 + few-shot）
- [x] `core/resume/parse.py`：`build_resume_parser(model, system_prompt)` + `run_resume_parser(agent, memory, resume_text) -> ResumeParseOutput`
- [x] 无 `LLM_API_KEY` 时 stub bypass（返回单条占位项目）
- [x] [gate] `uv run mypy src`

## 5. db.ops：简历 + 资料 + session

- [x] `db/ops.py` 加 `upsert_resume` / `get_resume`
- [x] `db/ops.py` 加 `apply_resume(document, *, ingest=False, user_id)`：清空重建——删除所有旧项目 + 旧简历笔记（tags 含 "resume"），用户手写笔记/claim/计划项的 project_id 置空，新建项目 + 每项目一条 note（tags=["resume"]）+ upsert_resume
- [x] `db/ops.py` 加 `list_drill_materials` / `upsert_drill_material` / `delete_drill_material`
- [x] `db/ops.py` 加 `create_drill_session` / `continue_drill_session`（追加 message）/ `list_drill_sessions` / `get_drill_session`
- [x] [gate] `uv run pytest tests/test_day_ops.py`（回归）

## 6. Sage 改造

- [x] `core/agents/sage.py`：`build_prompt` / `run_sage` 改签名（消费 `resume` + `materials` + `project` + `round_` + `direction`）
- [x] `core/agents/sage.py`：stub bypass 按轮次生成开场白 / done
- [x] `prompts/sage.md`：加轮次分档（tech_1~4 / hr）+ direction hint 注入段
- [x] [gate] `uv run mypy src`

## 7. REST 路由

- [x] `api/routes.py` 加 `POST /v1/resumes/upload`（multipart，存 `uploads/{upload_id}.ext`，extract + parse，返回 `{upload_id, document}`）
- [x] `api/routes.py` 加 `POST /v1/resumes/apply`（`{upload_id, document, ingest=false}` → `apply_resume`）
- [x] `api/routes.py` 加 `GET /v1/resumes`（当前简历）
- [x] `api/routes.py` 加 `GET/POST/PATCH/DELETE /v1/drill/materials`
- [x] `api/routes.py` 加 `POST /v1/drill/sessions`（`{round, direction?, project_id?}` → 建 session + 首轮 verdict）
- [x] `api/routes.py` 加 `POST /v1/drill/sessions/{id}`（`{answer}` → continue + 追加 message）
- [x] `api/routes.py` 加 `GET /v1/drill/sessions` / `GET /v1/drill/sessions/{id}`
- [x] **移除** `POST /v1/projects`（手动新建）；**移除** `POST /v1/projects/{id}/drill`（被 session 取代）；保留 `GET /v1/projects`、`GET/PATCH /v1/projects/{id}`、`GET /v1/projects/{id}/progress`
- [x] 文件大小/扩展名校验（≤10MB，pdf/docx/txt/md）
- [x] [gate] `uv run mypy src && uv run pytest`

## 8. MCP 对等

- [x] `mcp/server.py` 加 `gotit_upload_resume` / `gotit_apply_resume` / `gotit_get_resume`
- [x] `mcp/server.py` 加 `gotit_list_drill_materials` / `gotit_upsert_drill_material` / `gotit_delete_drill_material`
- [x] `mcp/server.py` 加 `gotit_start_drill_session` / `gotit_continue_drill_session` / `gotit_list_drill_sessions` / `gotit_get_drill_session`
- [x] [gate] `uv run mypy src`

## 9. 端到端测试

- [x] `tests/test_resume.py` e2e：upload（fixture .txt）→ document → apply（ingest=false）→ 校验 projects/notes 落库、无 claim
- [x] `tests/test_resume.py` 覆盖重建：先 apply 一份 → 再 apply 新版 → 旧项目+旧简历笔记删除、新项目新建、用户手写笔记 project_id 置空保留
- [x] `tests/test_drill.py` materials CRUD：create/list/update/delete
- [x] `tests/test_drill.py` session e2e：start（round=tech_2, direction="偏架构"）→ 首轮 verdict → answer → continue → done；messages 落库
- [x] 无 LLM key 时 stub bypass 路径覆盖（解析 + session）
- [x] [gate] `uv run pytest tests/test_resume.py tests/test_drill.py`

## 10. 前端：DrillPage 重设计

- [x] `web/src/api.ts` 加 resumes / drill materials / drill sessions 端点
- [x] `web/src/store.tsx` 加 `resume` / `drillMaterials` / `drillSessions` / `activeDrillSession` 状态 + actions
- [x] `web/src/components/ResumeUploadModal/`：文件 tab 上传 → 解析预览（项目列表可编辑）→ 已有简历时二次确认 → apply
- [x] `web/src/components/DrillMaterialModal/`：资料列表 + 新建/编辑/删除（title + body）
- [x] `web/src/components/SessionStartPanel/`：轮次 5 段选择 + 方向输入 + 可选项目聚焦下拉
- [x] `web/src/pages/DrillPage/`：顶部简历状态 + 上传/资料入口；无 session → SessionStartPanel + 历史 session 列表；session 激活 → ChatLog + Composer
- [x] **移除**手动新建项目 modal 与项目 chip 区 `+` 按钮；保留项目编辑 modal
- [x] [gate] `cd web && npm run build`

## 11. 前端：project_id 串联

- [x] `onSaveNote` / `onGotItMaterial` 传 `selectedProjectId`
- [x] 侧栏项目 chip 点击 → DrillPage 新建 session 时预填聚焦项目；同时筛选今日 notes（按 `project_id`）
- [x] [gate] `cd web && npm run build`

## 12. skills / AGENTS 同步

- [x] `skills/gotit/SKILL.md` 加 resume / drill materials / drill sessions 工具说明
- [x] [gate] `./scripts/gate.sh`

## 13. 收尾

- [x] [gate] `./scripts/gate.sh` 全绿（ruff + mypy + pytest + harness dev set）
- [x] 同步 OpenSpec 三文件与实现一致
- [x] 归档到 `openspec/changes/archive/2026-07-28-resume-upload-parse/`（提交前）
