# Tasks — resume import & drill UX (evening session, consolidated)

## 后端解析
- [x] extract.py：TXT/MD UTF-8→GB18030 回退；PDF PyMuPDF 优先 + pypdf 兜底
- [x] pyproject.toml：加 pymupdf；mypy fitz ignore
- [x] heuristic.py：规则解析器（basics + 分段 + 项目切分）
- [x] parse.py：stub_parse 委托 heuristic，移除 [:500] 截断
- [x] heuristic：工作经历不混入项目（只项目经历映射；无项目经历才兜底）

## 后端简历原文件 + file_path 修复
- [x] upload 返回 file_path（含 ext）；ResumeApplyRequest 加 file_path；apply 用 body.file_path 落库
- [x] GET /v1/resumes/file 端点（FileResponse + ext→media_type，旧记录 glob 兜底）

## 后端深挖资料文件导入
- [x] POST /v1/drill/materials/upload 端点（复用 extract_text，返回 {title,body} 预览不落库）

## 前端
- [x] ResumeUploadModal：uploading loading + 遮罩 spinner + wide + 分区 + 项目增删 + 文件名回显 + apply 传 file_path
- [x] Modal：wide 变体
- [x] Sidebar：胶囊→纵向列表；项目区 + 号导入入口；点项目切 drill tab；projectPicked 默认无高亮
- [x] DrillPage：移除右上导入按钮；深挖资料→资料管理按钮；icon 换 SVG；加「查看简历」按钮
- [x] SessionStartPanel：原生 select→自定义下拉；默认轮次 tech_1；顶部「聚焦上下文」块（projectPicked 时显示）
- [x] DrillMaterialModal：编辑区加文件导入按钮 + 局部 loading + 错误提示 + 回填编辑器
- [x] ResumeViewerModal（新增）：blob fetch + PDF iframe / TXT MD pre / DOCX 下载
- [x] store：onApplyResume 加 filePath；onImportMaterialFile；showResumeViewer；projectPicked
- [x] api.ts：fetchBlob helper
- [x] types.ts：ResumeUploadResponse.file_path

## 测试
- [x] GBK 回退 / CJK PDF 提取 / heuristic 结构化 / 工作经历不混入 / 兜底
- [x] drill material upload：txt 提取 / 415 / 上传后保存 e2e
- [x] resume file：file_path 含 ext；file 端点 200/404；既有 apply 调用补 file_path

## Gate
- [x] ruff + mypy + pytest(29) + npm build 全绿
- [x] 真实 PDF 端到端验证
- [x] 归档（合并为单一 change）
