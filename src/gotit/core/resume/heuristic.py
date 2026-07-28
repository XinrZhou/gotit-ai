"""Heuristic resume parser — rule-based fallback when no LLM is configured.

Industry hybrid-pipeline practice: deterministic rules for high-confidence
fields (phone, email, name, section segmentation, project splitting) and
leave semantic fields for LLM refinement. This module never imports LLM /
framework code so it stays usable in tests and MCP without network.

It is intentionally tolerant: when structure is unclear it falls back to a
single placeholder project holding the full text, so the user can still
review/edit in the preview modal.
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID, uuid4

from gotit.core.models import ResumeBasics, ResumeDocument, ResumeParseOutput, ResumeProject

# Section headers we recognise. A line is treated as a header when it (after
# stripping leading #'s and whitespace) equals or starts with one of these
# and is short enough to plausibly be a heading rather than a bullet.
_SECTION_HEADERS: tuple[str, ...] = (
    "工作经历",
    "工作经验",
    "项目经历",
    "项目经验",
    "项目",
    "实习经历",
    "教育经历",
    "教育背景",
    "专业技能",
    "技能特长",
    "技能",
    "自我评价",
    "个人简介",
    "个人优势",
    "荣誉奖项",
    "证书",
    "获奖",
)

# Sections that represent distinct projects (project experience).
_PROJECT_SECTIONS: tuple[str, ...] = ("项目经历", "项目经验", "项目")

# Sections that represent employment history (company + role + tenure).
# These are NOT projects; only used as a fallback when a resume has no
# 项目经历 section at all, so we don't lose everything.
_WORK_SECTIONS: tuple[str, ...] = ("工作经历", "工作经验", "实习经历")

_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[-\s]?)?1[3-9]\d{9}(?:[-\s]?\d{3,4})?")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_DATE_RE = re.compile(
    r"\d{4}[.\-/年]\d{1,2}[.\-/月]?"
    r"(?:\s*[—\-~至]+\s*\d{4}[.\-/年]\d{1,2}[.\-/月]?|至今|现在|present)?",
    re.I,
)
_ROLE_HINT_RE = re.compile(r"^(?:角色|职位|岗位|职务)\s*[:：|｜]\s*(.+)$")
_TECH_HINT_RE = re.compile(r"^(?:技术栈|技术|技能|栈)\s*[:：|｜]\s*(.+)$")
_GOAL_HINT_RE = re.compile(r"^(?:目标|目的|背景)\s*[:：|｜]\s*(.+)$")
_HEADER_PREFIX_RE = re.compile(r"^[#>\-\s]*")


def heuristic_parse(*, upload_id: Any, resume_text: str) -> ResumeParseOutput:
    """Rule-based structured parse. Best-effort; never raises on bad input."""
    uid: Any = upload_id
    if not isinstance(uid, UUID):
        uid = uuid4()

    lines = [ln.strip() for ln in resume_text.splitlines() if ln.strip()]
    if not lines:
        return _placeholder(uid, resume_text)

    basics = _extract_basics(lines)
    sections = _segment_sections(lines)
    projects = _extract_projects(sections)

    if not projects:
        # No structured project section found — keep the full text as one
        # placeholder so the user can still review/edit everything.
        projects = [ResumeProject(name="占位项目", description=resume_text.strip())]

    return ResumeParseOutput(
        upload_id=uid,
        document=ResumeDocument(basics=basics, projects=projects),
    )


def _placeholder(uid: Any, resume_text: str) -> ResumeParseOutput:
    return ResumeParseOutput(
        upload_id=uid,
        document=ResumeDocument(
            projects=[ResumeProject(name="占位项目", description=resume_text.strip())]
        ),
    )


def _extract_basics(lines: list[str]) -> ResumeBasics:
    name: str | None = None
    for ln in lines[:4]:
        bare = ln.strip()
        if not bare:
            continue
        if _EMAIL_RE.search(bare) or _PHONE_RE.search(bare):
            continue
        if _is_header(bare) or bare.startswith(("•", "-", "|", "｜", "#")):
            continue
        if len(bare) > 12:
            continue
        name = bare
        break

    target_role: str | None = None
    for ln in lines[:12]:
        for kw in ("目标岗位", "求职意向", "意向岗位", "目标职位", "期望岗位", "求职目标"):
            if kw in ln:
                after = re.split(r"[:：|｜]", ln, maxsplit=1)
                if len(after) > 1 and after[1].strip():
                    target_role = after[1].strip()
                else:
                    target_role = ln.replace(kw, "").strip(" :：|｜-")
                break
        if target_role:
            break

    if not target_role:
        # Fallback: scan the contact block (first few lines) for a role-like
        # segment separated by | / ｜ — common in Chinese resumes that put the
        # current/target title next to phone + email.
        role_kw = re.compile(
            r"(工程师|开发|架构|设计|经理|主管|总监|专员|实习|顾问|科学家|研究员|负责人)"
        )
        for ln in lines[:6]:
            for seg in re.split(r"[|｜]", ln):
                seg = seg.strip()
                if not seg or _EMAIL_RE.search(seg) or _PHONE_RE.search(seg):
                    continue
                if seg in ("杭州", "北京", "上海", "深圳", "广州", "成都", "杭州", "南京", "苏州"):
                    continue
                if role_kw.search(seg):
                    target_role = seg
                    break
            if target_role:
                break

    return ResumeBasics(name=name, target_role=target_role)


def _is_header(line: str) -> bool:
    bare = _HEADER_PREFIX_RE.sub("", line).strip()
    if len(bare) > 12:
        return False
    return any(bare == h or bare.startswith(h) for h in _SECTION_HEADERS)


def _segment_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """Split lines into ordered (header, body_lines) segments.

    Lines before the first recognised header are attached to a "" preamble
    (contact / name block) and not returned as a section.
    """
    sections: list[tuple[str, list[str]]] = []
    current: tuple[str, list[str]] | None = None
    for ln in lines:
        if _is_header(ln):
            if current is not None:
                sections.append(current)
            current = (_HEADER_PREFIX_RE.sub("", ln).strip(), [])
        elif current is not None:
            current[1].append(ln)
    if current is not None:
        sections.append(current)
    return sections


def _extract_projects(sections: list[tuple[str, list[str]]]) -> list[ResumeProject]:
    # Primary: only the 项目经历 / 项目经验 / 项目 sections are real projects.
    # Work-experience entries (company + role + tenure) are semantically not
    # projects, so we keep them out of the project list.
    projects: list[ResumeProject] = []
    for header, body in sections:
        if not any(header.startswith(h) or header == h for h in _PROJECT_SECTIONS):
            continue
        projects.extend(_split_entries(body, header))

    if projects:
        return projects

    # Fallback: resume has no 项目经历 section. Use 工作经历 / 工作经验 / 实习经历
    # entries as projects so the user still gets structured items to edit,
    # rather than a single placeholder blob.
    for header, body in sections:
        if not any(header.startswith(h) or header == h for h in _WORK_SECTIONS):
            continue
        projects.extend(_split_entries(body, header))
    return projects


def _split_entries(body: list[str], section_name: str) -> list[ResumeProject]:
    """Split a project/work section body into individual entries.

    A new entry starts at a title line (``###`` heading or a ``name|role``
    separator line). Body lines accumulate into the current entry; any
    preamble before the first title is dropped.
    """
    entries: list[list[str]] = []
    for ln in body:
        if _looks_like_title(ln):
            entries.append([ln])
        elif entries:
            entries[-1].append(ln)
    # orphan title with no body → drop
    entries = [e for e in entries if len(e) > 1 or not _looks_like_title(e[0])]

    projects: list[ResumeProject] = []
    for entry in entries:
        proj = _entry_to_project(entry, section_name)
        if proj is not None:
            projects.append(proj)
    return projects


def _looks_like_title(line: str) -> bool:
    bare = line.strip()
    if not bare or bare.startswith(("•", "-", "·")):
        return False
    if bare.startswith(("###", "##", "#")):
        return True
    # name|role or name｜role separator → title
    return ("|" in bare or "｜" in bare) and not _DATE_RE.fullmatch(bare)


def _entry_to_project(entry: list[str], section_name: str) -> ResumeProject | None:
    if not entry:
        return None
    title = entry[0]
    rest = entry[1:]

    name: str
    role: str | None = None
    # Split title on | / ｜ → name | role
    parts = re.split(r"[|｜]", title, maxsplit=1)
    name = parts[0].strip(" #:-：").strip()
    if len(parts) > 1:
        role = parts[1].strip()
        # role may contain location after another separator; keep first chunk
        role = re.split(r"[|｜]", role)[0].strip()

    tech_stack: list[str] = []
    goal: str | None = None
    desc_lines: list[str] = []
    for ln in rest:
        m = _ROLE_HINT_RE.match(ln)
        if m and not role:
            role = m.group(1).strip()
            continue
        m = _TECH_HINT_RE.match(ln)
        if m:
            tech_stack = _split_tech(m.group(1))
            continue
        m = _GOAL_HINT_RE.match(ln)
        if m:
            goal = m.group(1).strip()
            continue
        desc_lines.append(ln)

    description = "\n".join(desc_lines).strip()
    if not name:
        name = section_name
    return ResumeProject(
        name=name,
        role=role or None,
        goal=goal,
        tech_stack=tech_stack,
        description=description,
    )


def _split_tech(raw: str) -> list[str]:
    # split on common tech-stack separators only; do NOT split on whitespace
    # (multi-word stack names like "Claude Agent SDK" must stay intact).
    items = re.split(r"[·,，、/|｜]+", raw)
    return [s.strip() for s in items if s.strip()]
