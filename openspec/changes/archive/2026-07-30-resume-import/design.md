# resume-import — design

## Decisions

1. **File-backed resume prompt** — `load_resume_system_prompt()` reads
   `prompts/resume.md` via `gotit.prompts` helpers. Do not use
   `get_active_prompt("compass")` for resume parse (wrong task + version fight).
2. **Clip at 12k chars** — keep ~2/3 head + ~1/3 tail with a clear marker so
   early basics and late projects both survive. Clip applies only to the LLM
   path; heuristic stub still sees full text (cheap).
3. **Frontmatter** — `agent: resume` so future DB registration does not overwrite
   compass `v1` active state.
4. **Import owns projects + ResumeRecord only** — Notes/claims remain the
   learner’s hand-written / curated path. Sage already receives
   `resume=ResumeDocument` in drill sessions — no note bridge required.
5. **Legacy purge** — On apply, still delete notes with `tags` containing
   `resume` so prior imports do not leave stale 「还没出题」 rows.
