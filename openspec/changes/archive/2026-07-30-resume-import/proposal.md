# resume-import — 简历解析加速 + 导入不进笔记队列

## Why

简历上传慢（错用 compass prompt、长文全量送 LLM），且 `apply_resume` 曾为每个
项目造一条 `tags=["resume"]` 笔记，污染「还没出题」。深挖只应读
`ResumeDocument.projects`，不该走 notes → claims 测验队列。

## Scope

### In

- 始终从 `prompts/resume.md` 加载解析 system prompt（API + MCP）
- 超长正文 clip（head+tail）再送 LLM；收紧 `resume.md` 抽取措辞
- `apply_resume`：只建 projects + upsert resume；重建时仍清遗留 resume 笔记；
  不再新建笔记；`ingest` 对该路径 no-op
- 测试 / MCP docstring / SYSTEM / skill 文案对齐

### Out

- 真异步后台解析 / 流式预览
- 用笔记桥接 Sage drill

## Verification

- `uv run pytest`（resume 相关）
- 手动：上传解析更快且项目结构合理；导入后 Library 无 resume 笔记；深挖仍可读项目
