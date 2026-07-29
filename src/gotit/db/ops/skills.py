"""User + builtin skill catalog (Settings / chat tray)."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import SkillDetail, SkillInfo
from gotit.core.skills import SKILLS_DIR, load_skill
from gotit.core.skills import list_skills as list_builtin_names
from gotit.db.models import UserSkillRow
from gotit.prompts import _parse_frontmatter

_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,62}$")


def _builtin_notes(name: str) -> str | None:
    path = SKILLS_DIR / f"{name}.md"
    if not path.is_file():
        return None
    meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
    return meta.get("notes") or None


def _format_skill_markdown(name: str, notes: str | None, body: str) -> str:
    lines = ["---", f"skill: {name}"]
    if notes:
        lines.append(f"notes: {notes}")
    lines.extend(["---", "", body.strip(), ""])
    return "\n".join(lines)


def parse_skill_markdown(
    raw: str, *, fallback_name: str | None = None
) -> tuple[str, str, str | None]:
    """Return (name, body, notes) from a SKILL.md / skill markdown blob."""
    meta, body = _parse_frontmatter(raw)
    name = (meta.get("skill") or meta.get("name") or fallback_name or "").strip()
    if not name or not _NAME_RE.match(name):
        raise ValueError(
            "skill name missing or invalid — use frontmatter `skill: my-name` "
            "(letters, digits, _-; start with a letter)"
        )
    if not body.strip():
        raise ValueError("skill body is empty")
    notes = meta.get("notes") or meta.get("description") or None
    return name, body.strip(), notes


async def list_skill_catalog(
    session: AsyncSession,
    *,
    user_id: str,
) -> list[SkillInfo]:
    """Merge disk builtins with per-user DB rows (enabled / user installs)."""
    result = await session.execute(
        select(UserSkillRow).where(UserSkillRow.user_id == user_id)
    )
    rows = {r.name: r for r in result.scalars().all()}

    out: dict[str, SkillInfo] = {}
    for name in list_builtin_names():
        row = rows.get(name)
        out[name] = SkillInfo(
            name=name,
            notes=(row.notes if row and row.notes else _builtin_notes(name)),
            enabled=True if row is None else bool(row.enabled),
            source="user" if row and row.source == "user" and row.body else "builtin",
        )

    for name, row in rows.items():
        if name in out:
            continue
        if row.source != "user" and not row.body:
            # orphaned builtin override for a deleted disk skill — skip
            continue
        out[name] = SkillInfo(
            name=name,
            notes=row.notes,
            enabled=bool(row.enabled),
            source="user",
        )

    return sorted(out.values(), key=lambda s: s.name)


async def get_skill_detail(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
) -> SkillDetail:
    """Return skill markdown for Settings view/edit."""
    catalog = await list_skill_catalog(session, user_id=user_id)
    info = next((s for s in catalog if s.name == name), None)
    if info is None:
        raise KeyError(f"skill '{name}' not found")

    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None and row.body:
        markdown = _format_skill_markdown(name, row.notes or info.notes, row.body)
        return SkillDetail(
            name=info.name,
            notes=info.notes,
            enabled=info.enabled,
            source=info.source,
            markdown=markdown,
            editable=True,
        )

    path = SKILLS_DIR / f"{name}.md"
    if path.is_file():
        markdown = path.read_text(encoding="utf-8")
    else:
        body = load_skill(name) or ""
        markdown = _format_skill_markdown(name, info.notes, body) if body else ""
    return SkillDetail(
        name=info.name,
        notes=info.notes,
        enabled=info.enabled,
        source=info.source,
        markdown=markdown,
        editable=info.source == "user",
    )


async def resolve_skill_body(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
) -> str | None:
    """Load skill body if enabled; prefer user DB body over disk."""
    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    if row is not None and not row.enabled:
        return None
    if row is not None and row.body:
        return row.body
    # Disabled builtin with no row body is already handled; missing row = enabled builtin
    if row is None or row.enabled:
        return load_skill(name)
    return None


async def install_skill(
    session: AsyncSession,
    *,
    user_id: str,
    raw_markdown: str,
    fallback_name: str | None = None,
) -> SkillInfo:
    name, body, notes = parse_skill_markdown(raw_markdown, fallback_name=fallback_name)
    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        row = UserSkillRow(
            user_id=user_id,
            name=name,
            body=body,
            notes=notes,
            enabled=True,
            source="user",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.body = body
        row.notes = notes
        row.enabled = True
        row.source = "user"
        row.updated_at = now
    await session.flush()
    return SkillInfo(name=name, notes=notes, enabled=True, source="user")


async def update_skill_markdown(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
    raw_markdown: str,
) -> SkillInfo:
    """Replace body of an existing user skill (name in frontmatter must match)."""
    parsed_name, body, notes = parse_skill_markdown(raw_markdown, fallback_name=name)
    if parsed_name != name:
        raise ValueError(f"skill name in markdown must stay '{name}'")
    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not row.body or row.source != "user":
        raise ValueError(f"skill '{name}' is not a user-editable install")
    now = datetime.now(UTC)
    row.body = body
    row.notes = notes
    row.updated_at = now
    await session.flush()
    return SkillInfo(
        name=name,
        notes=notes,
        enabled=bool(row.enabled),
        source="user",
    )


async def set_skill_enabled(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
    enabled: bool,
) -> SkillInfo:
    builtins = set(list_builtin_names())
    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if row is None:
        if name not in builtins:
            raise KeyError(f"skill '{name}' not found")
        row = UserSkillRow(
            user_id=user_id,
            name=name,
            body=None,
            notes=_builtin_notes(name),
            enabled=enabled,
            source="builtin",
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.enabled = enabled
        row.updated_at = now
    await session.flush()

    catalog = await list_skill_catalog(session, user_id=user_id)
    for item in catalog:
        if item.name == name:
            return item
    raise KeyError(f"skill '{name}' not found")


async def delete_user_skill(
    session: AsyncSession,
    *,
    user_id: str,
    name: str,
) -> None:
    result = await session.execute(
        select(UserSkillRow).where(
            UserSkillRow.user_id == user_id,
            UserSkillRow.name == name,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise KeyError(f"skill '{name}' not found")
    if row.source != "user" or not row.body:
        # builtin override only — delete row to restore default enabled
        await session.delete(row)
        await session.flush()
        return
    # If it shadowed a builtin, removing user body restores builtin
    builtins = set(list_builtin_names())
    if name in builtins:
        row.body = None
        row.source = "builtin"
        row.enabled = True
        row.notes = _builtin_notes(name)
        row.updated_at = datetime.now(UTC)
    else:
        await session.delete(row)
    await session.flush()
