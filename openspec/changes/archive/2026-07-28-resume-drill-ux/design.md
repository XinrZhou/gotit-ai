# Design — resume import & drill UX (evening session, consolidated)

## 解析分层

```
上传文件 (multipart / 文件路径)
  ↓
core/resume/extract.py   — 文本提取（PyMuPDF / python-docx / UTF-8→GB18030）→ 纯文本
  ↓
core/resume/parse.py     — 有 LLM_API_KEY 走 Compass；否则 heuristic_parse
  ↓
预览编辑（前端可改）
  ↓
db.ops.apply_resume()    — 按项目重建项目库 + 每项目一条 resume note
```

- **PyMuPDF 优先**：pypdf 对嵌入子集字体 ToUnicode CMap 解析弱，中文/自定义字体 PDF 吐字形码 mojibake；fitz 正确解析。pypdf 纯 Python 兜底。
- **heuristic 兜底**：无 LLM 时用规则做基础结构化（姓名/岗位/section 分段/项目切分），让用户看到大致结构可编辑。只「项目经历」映射 projects；工作经历不混入（无项目经历时才兜底）。

## 简历原文件查看 + file_path 修复

```
upload:  writes uploads/{upload_id}.{ext}, returns {upload_id, file_path, document}
apply:   ResumeApplyRequest{upload_id, document, file_path, ingest}
         → ResumeRow.file_path = "uploads/{id}.{ext}"  ✓（修了原本无 ext 的 bug）

GET /v1/resumes/file  (require_api_key)
  → 200 FileResponse(path=ResumeRow.file_path, media_type=<by ext>)
  → 404 无简历 / 文件丢失（旧记录 glob uploads/{upload_id}.* 兜底）
```

ext → media_type：pdf→application/pdf；docx→ooxml；txt→text/plain；md→text/markdown。

## 深挖资料文件导入

```
POST /v1/drill/materials/upload  (multipart, require_api_key)
  file: UploadFile → extract_text → {title, body} 预览（不落库）
  → 413 too large / 415 unsupported / 422 extract error
```

一步式（无 apply 阶段）：回填 DrillMaterialModal 编辑器，用户过目可编辑后点现有「添加」走原 upsert，零新 DB 路径。

## 前端 IA

- 侧栏「项目」= 项目一览 + 导入入口（+）+ 项目浏览器：点项目 → 切 drill tab + 聚焦 + 展示该项目简历内容。`projectPicked` 标志使默认无高亮（避免「全部」初始就被高亮）。
- drill tab「聚焦项目」下拉 = session 级聚焦微调（与侧栏联动）；顶部「聚焦上下文」块展示该项目简历内容或整份简历概览。
- 「资料管理」按钮 = 深挖资料 CRUD + 文件导入入口；icon 用 inline SVG。
- 「查看简历」按钮 = ResumeViewerModal，按 ext 分流渲染。

## ResumeViewerModal 渲染分流

- iframe src 无法带 Bearer header → 用 fetch(headers) 取 blob → `URL.createObjectURL`。
- PDF → `<iframe src={objUrl}>` 全幅原生渲染。
- TXT/MD → `await res.text()` → `<pre>`。
- DOCX → object URL → 「下载 DOCX」按钮（浏览器下载，无法原生预览）。
- 关闭 `URL.revokeObjectURL`。类型由 `resume.file_path` 扩展名判定。

## REST ↔ MCP parity

`extract_text` / `heuristic_parse` / `apply_resume` / drill material upload / resume file 均为 core 共用或 REST 先行；MCP 对应工具可后续补，签名对齐。

## Risks

- heuristic 对非典型简历格式可能抽不全 → 用户在预览态可编辑/手动加项目兜底；配 LLM 后走 Compass 更准。
- 旧 ResumeRow.file_path 仍是坏的（无 ext）→ file 端点 glob 兜底。
- DOCX 无法浏览器原生预览 → 下载兜底。
- 提取文本可能很长 → DrillMaterial.body 无上限，桑迪消费时由 prompt 上下文窗口裁剪。
