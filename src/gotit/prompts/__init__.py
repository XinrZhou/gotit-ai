"""Prompt file loading: parse `prompts/*.md` (frontmatter + body) into DTOs.

Framework-free: only stdlib + pydantic. DB persistence lives in `gotit.db.ops`.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_DNS, UUID, uuid5

from gotit.core.models import PromptVersion


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    meta: dict[str, str] = {}
    i = 1
    while i < len(lines) and lines[i].strip() != "---":
        key, _, value = lines[i].partition(":")
        meta[key.strip()] = value.strip()
        i += 1
    body = "\n".join(lines[i + 1 :]).strip() if i < len(lines) else ""
    return meta, body


def load_prompt_file(path: Path) -> PromptVersion:
    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(raw)
    agent = meta.get("agent", path.stem)
    version = meta.get("version", "v1")
    notes = meta.get("notes")
    content_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return PromptVersion(
        id=prompt_id_for(agent, version),
        agent_name=agent,
        version_label=version,
        content_hash=content_hash,
        system_prompt=body,
        config={},
        notes=notes,
        created_at=datetime.now(UTC),
        is_active=False,
    )


def load_prompt_dir(prompts_dir: Path) -> list[PromptVersion]:
    files = sorted(prompts_dir.glob("*.md"))
    return [load_prompt_file(p) for p in files]


def prompt_id_for(agent: str, version: str) -> UUID:
    """Stable UUID per (agent, version) so re-registration upserts cleanly."""
    return uuid5(NAMESPACE_DNS, f"gotit-prompt:{agent}:{version}")

