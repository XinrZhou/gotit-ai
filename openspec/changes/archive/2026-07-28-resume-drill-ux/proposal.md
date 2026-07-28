# Proposal — resume import & drill UX (evening session, consolidated)

## Why

「导入简历 → 深挖项目」这条主路径在 2026-07-28 晚上一轮连续迭代里打磨到位。原本被拆成多个小 change，现合并为一条连贯记录。整晚驱动的几类问题：

1. 上传/解析无 loading 反馈；TXT 简历乱码（GBK 被当 UTF-8）；PDF 简历乱码（pypdf 字体 ToUnicode 弱）。
2. 弹窗太窄、描述被 `[:500]` 截断、不支持多项目；无 `LLM_API_KEY` 时 `stub_parse` 把全文堆进一个占位项目，结构化字段全空；工作经历被误并进项目经历。
3. 侧栏项目区样式（胶囊）丑、导入入口位置不直观、深挖资料按钮不像按钮；聚焦项目用原生 select 样式不统一、面试轮次默认选错（二面→应一面）；侧栏选项目无后续动作（不切到深挖 tab）。
4. 深挖资料（DrillMaterial）只能手写粘贴，希望直接导入 PDF/DOCX/TXT/MD 文件。
5. 想直接查看导入的简历原文件（PDF 原样渲染、DOCX 下载、TXT/MD 看文本）。

## Scope（整晚合并范围）

### 后端解析
- `core/resume/extract.py`：TXT/MD 解码 UTF-8 严格优先 + GB18030 回退；PDF 提取切到 PyMuPDF (fitz)，pypdf 兜底。
- `core/resume/heuristic.py`（新增）：无 LLM 时的规则解析器——basics（姓名/目标岗位）+ section 分段 + 项目切分；只把「项目经历」映射成 projects，工作经历不混入（无项目经历时才兜底）。
- `core/resume/parse.py`：`stub_parse` 委托 `heuristic_parse`，移除 `[:500]` 截断。
- `pyproject.toml`：加 `pymupdf>=1.28.0`；mypy `fitz` ignore_missing_imports。

### 后端简历原文件查看 + file_path 修复
- 修 bug：`apply_resume` 之前存 `file_path=f"uploads/{upload_id}"`（无扩展名），实际文件在 `uploads/{upload_id}.{ext}`，路径损坏。现 upload 返回 `file_path`（含扩展名），`ResumeApplyRequest` 加 `file_path`，apply 用 `body.file_path` 落库。
- 新端点 `GET /v1/resumes/file`：读 `ResumeRow.file_path` → `FileResponse`，content-type 由扩展名映射（pdf/docx/txt/md）；旧记录 file_path 坏的用 glob `uploads/{upload_id}.*` 兜底；无简历/文件丢失 → 404。

### 后端深挖资料文件导入
- 新端点 `POST /v1/drill/materials/upload`：multipart 文件 → 复用 `extract_text` → 返回 `{title, body}` 预览（不落库），复用 `ALLOWED_RESUME_TYPES` + `MAX_RESUME_BYTES`。title = 文件名去扩展名。

### 前端
- `ResumeUploadModal`：本地 `uploading` loading + 遮罩 spinner；`wide` 弹窗 + body 滚动；分区标题；项目卡删除 + 「+ 添加项目」；文件名回显；apply 传 file_path。
- `Modal`：新增 `wide` 变体。
- `Sidebar`：项目区胶囊→纵向列表（左竖条选中态）；「项目」标题右侧 + 号导入入口；点项目切 drill tab；`projectPicked` 标志使默认无高亮。
- `DrillPage`：移除右上导入按钮（入口移至侧栏）；「深挖资料」→「资料管理」明显按钮；icon 由 📖 emoji 换 inline SVG；简历状态旁加「查看简历」按钮。
- `SessionStartPanel`：原生 select→自定义下拉；默认轮次 tech_2→tech_1；顶部加「聚焦上下文」块（聚焦项目展示 name/role/tech_stack + resume 描述；整份简历展示 basics 概览），仅 `projectPicked` 时显示。
- `DrillMaterialModal`：编辑区加「导入文件」按钮 + 局部 loading + 错误提示 + 回填编辑器（导入后可编辑再点现有「添加」保存）。
- `ResumeViewerModal`（新增）：带 auth 的 fetch 取 blob → object URL；PDF→iframe 原样渲染；TXT/MD→pre；DOCX→下载按钮；关闭 revokeObjectURL。
- `store.tsx`：`onApplyResume` 加 filePath 参数；`onImportMaterialFile`；`showResumeViewer` 状态；`projectPicked` 标志；`onSelectDrillSession` 置 picked。
- `api.ts`：新增 `fetchBlob` helper。
- `types.ts`：`ResumeUploadResponse.file_path`。

### 测试
- GBK 回退 / CJK PDF 提取 / heuristic 结构化 / 工作经历不混入 / 兜底。
- drill material upload：txt 提取 / 不支持类型 415 / 上传后保存 e2e。
- resume file：file_path 含 ext；file 端点 200/404；既有 apply 调用补 file_path。

## Out of scope

- ZIP 批量导入（NoteComposeModal 占位提过，不做）。
- DayNote（侧栏学习资料）文件导入（另一条线，NoteComposeModal 文件 tab 占位）。
- DOCX 在浏览器原生渲染（用下载兜底）。
- MCP 对应工具（REST 先行）。

## Verification

- `uv run ruff check .` / `uv run mypy src` / `uv run pytest`（29 passed）/ `cd web && npm run build` 全绿。
- 真实 PDF 端到端：导入 → 解析正确（姓名/岗位/多项目）→ 查看简历 iframe 渲染 → 深挖资料导入文件。
