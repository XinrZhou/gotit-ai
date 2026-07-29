"""Skills layer — on-demand prompt fragments injected into an agent's context.

A skill is a markdown file under `prompts/skills/<name>.md` (frontmatter + body).
When a learner requests a skill by name (e.g. via the chat surface), the skill's
body is appended to the addressed agent's system prompt for that turn — letting
the companion switch modes (debug / review / drill …) without a different agent.

Framework-free: only stdlib. The loader resolves the skills dir relative to the
repo root (parents[3] from this file → repo root → prompts/skills).
"""

from __future__ import annotations

from pathlib import Path

from gotit.prompts import _parse_frontmatter

SKILLS_DIR = Path(__file__).resolve().parents[4] / "prompts" / "skills"


def load_skill(name: str) -> str | None:
    """Return the body of `prompts/skills/<name>.md`, or None if it doesn't exist."""
    path = SKILLS_DIR / f"{name}.md"
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    _, body = _parse_frontmatter(raw)
    return body


def list_skills() -> list[str]:
    """Available skill names (file stems under prompts/skills/)."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(p.stem for p in SKILLS_DIR.glob("*.md"))
