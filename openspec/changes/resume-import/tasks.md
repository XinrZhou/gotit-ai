# resume-import — tasks

## Spec

- [x] proposal / design / tasks（合并自 `resume-parse-fast` + `resume-no-notes`）

## Parse fast

- [x] `load_resume_system_prompt` + `clip_resume_text` in `core/resume/parse.py`
- [x] Wire API + MCP upload paths
- [x] Update `prompts/resume.md`（agent: resume, tighter rules）
- [x] Unit tests for clip + prompt load
- [x] LLM `output_type` = `ResumeDocument`（not full `ResumeParseOutput`）

## No quiz notes

- [x] `apply_resume` stop creating notes; purge legacy resume notes
- [x] Fix `tests/test_resume.py`
- [x] MCP / SKILL / SYSTEM wording
