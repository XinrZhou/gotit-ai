# Resume-driven drill — 简历驱动的模拟面试深挖

> **Status: proposed 2026-07-28**（未实现，重写自原 `resume-upload-parse`）

## Why

gotit-ai 的「项目深挖」当前是"点一个手动建的项目卡片 → 桑迪追问这一个项目"。这跟社招备考的真实形态对不上：真实面试官是**看着你整份简历**、挑项目往下深挖的，而且分轮次（一面偏广度、二面偏深度、三/四面偏架构、HR 面偏行为）。同时用户备考时会自己整理"这个项目要怎么被深挖"的资料，agent 应该消费这些资料，而不是只靠一张项目卡片。

本变更把深挖从「按单个项目卡片」升级为「按简历维度的模拟面试」：

1. **导入简历**（全局一份，覆盖上传需二次确认）→ 解析出项目库（次级视图，可校验/编辑/可选聚焦）
2. **导入深挖资料**（全局多份，可导入/编辑/删除）→ 作为面试官的消费上下文
3. **模拟面试 session**：选面试轮次（技术一/二/三/四面 + HR 面）+ 补充方向（如"偏架构"）+ 可选聚焦某个项目 → 桑迪以该轮次面试官身份跨项目深挖；可新建 session 开新一轮

项目不再手动新建，只能由简历解析产生。深挖的 session 单元从"单个项目"变为"整份简历（可选聚焦某项目）"。

## Scope

### In

- **简历上传与解析**（重写自原方案）：
  - `POST /v1/resumes/upload`（multipart），支持 `.pdf` / `.docx` / `.txt` / `.md`，存 `uploads/`
  - 两阶段解析：文本提取（`core/resume/extract.py`，framework-free）+ 结构化解析（Compass 扩展，海绵宝宝人格）→ `ResumeDocument{basics, projects[]}`
  - `POST /v1/resumes/apply`：用户编辑后的 document 落库；**清空重建**——删除所有旧项目 + 旧简历笔记（`tags` 含 `resume`），新建解析出的项目 + 每项目一条 note（`tags=["resume"]`），默认不 ingest
  - 全局一份：再上传时前端二次确认，apply 后清空重建项目库；用户手写笔记/claim 不删除，但其 `project_id` 置空（脱离已删项目）
- **深挖资料 CRUD**：
  - `GET/POST/PATCH/DELETE /v1/drill/materials`，全局多份，可导入/编辑/删除
  - 存 `drill_materials` 表（title + body），作为面试官消费上下文
- **模拟面试 session**：
  - `POST /v1/drill/sessions`：`{round, direction?, project_id?}` 开新 session，返回 session + 首轮 verdict
  - `POST /v1/drill/sessions/{id}`：`{answer}` 继续追问，返回 verdict
  - `GET /v1/drill/sessions`（列表）/ `GET /v1/drill/sessions/{id}`（含消息）
  - session 持久化（`drill_sessions` 表 + messages JSONB），可回看 / 开新一轮
  - 轮次枚举：`tech_1` / `tech_2` / `tech_3` / `tech_4` / `hr`
- **Sage（桑迪）改造**：消费简历（parsed document）+ 深挖资料 + 可选聚焦项目 + 轮次人格 + 方向 hint；prompt 按轮次分档（技术轮走 drill ladder，HR 轮走行为面）
- **移除手动新建项目**：删除 `POST /v1/projects` 与前端「新建项目」modal/`+` chip；项目编辑保留；移除旧 `POST /v1/projects/{id}/drill`（被 session 取代）
- **MCP 对等**：`gotit_upload_resume` / `gotit_apply_resume` / `gotit_list_drill_materials` / `gotit_upsert_drill_material` / `gotit_delete_drill_material` / `gotit_start_drill_session` / `gotit_continue_drill_session` / `gotit_list_drill_sessions`
- **前端 DrillPage 重设计**：简历上传/预览/应用 + 资料管理 + session 列表 + 新建 session（轮次/方向/可选聚焦）+ 对话
- **project_id 串联**：手写笔记的 `onSaveNote` / `onGotItMaterial` 传 `selectedProjectId`；侧栏项目 chip 筛选 notes
- **依赖**：`pypdf`、`python-docx`
- **Alembic 迁移 0004**：`resumes` / `drill_materials` / `drill_sessions` 三张表
- **测试 + gate**：解析单测、session e2e、gate 集成

### Out

- 链接导入 / `.zip` 批量导入（后续迭代）
- 对象存储（M0 本地 `uploads/`）
- OCR（扫描版 PDF 明确报错，不接 OCR）
- 简历多版本管理（M0 全局一份，覆盖即替换）
- 简历结构化字段（公司/时间段/教育）——M0 只抽 `projects[]` + basics
- 自动 ingest / 自动加计划项（默认不 ingest）
- session 的跨设备同步优化（M0 单机）

## Non-goals

- 不取代手写笔记入口（手写仍是补充录入方式，保留）
- 不做简历模板匹配 / 简历评分（gotit 是检验台，不是简历优化工具）
- 不自动启动深挖 session（apply 后简历/项目就绪，用户自行开 session）
- 不保留手动新建项目（项目只能由简历上传产生；临时主题可上传只含一段描述的 .txt）

## Verification

- `./scripts/gate.sh` 通过（ruff + mypy + pytest + harness dev set）
- 简历端到端：上传样例简历 → `upload` 返回 `upload_id` + `ResumeDocument` → 用户编辑 → `apply` → 落库 N 个 Project（按名称合并）+ N 条 note（默认无 claim）。`tests/test_resume.py` 覆盖
  - 覆盖上传：已有简历时 `upload` 仍返回 document，前端二次确认后 `apply` 清空重建（旧项目 + 旧简历笔记删除，用户手写笔记/claim 的 project_id 置空保留）
- 深挖资料 CRUD：`tests/test_drill.py` 覆盖 create/list/update/delete
- session 端到端：开 session（round=tech_2, direction="偏架构"）→ 首轮 verdict → answer → 继续 → done。`tests/test_drill.py` 覆盖
- 无 LLM key 时 stub bypass：解析返回占位项目、session 返回 stub 追问，gate 在 CI 无 key 环境跑通
- 前端：上传 → 预览 → 确认 → 项目库出现新项目 + 今日资料出现新笔记；DrillPage 可开 session 对话（`cd web && npm run build`）
- 手动新建入口已移除：项目库无「新建」按钮，编辑入口仍可改字段
