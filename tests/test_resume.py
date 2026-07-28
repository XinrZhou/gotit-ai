"""Tests for resume text extraction and (stub) parse + apply."""
from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient

from gotit.core.resume.extract import ResumeExtractError, extract_text

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_text_plain() -> None:
    content = (FIXTURES / "sample.txt").read_bytes()
    text = extract_text(content, "text/plain")
    assert "订单中台重构" in text
    assert "风控引擎" in text


def test_extract_text_markdown() -> None:
    content = b"# Resume\n\n- item one\n- item two\n"
    text = extract_text(content, "text/markdown")
    assert "Resume" in text and "item one" in text


def test_extract_text_gbk_fallback() -> None:
    """GBK-encoded Chinese resumes must decode correctly, not produce mojibake."""
    content = (FIXTURES / "sample-gbk.txt").read_bytes()
    # Sanity: the fixture really is non-UTF-8.
    with pytest.raises(UnicodeDecodeError):
        content.decode("utf-8")
    text = extract_text(content, "text/plain")
    assert "张三" in text
    assert "订单中台重构" in text
    assert "�" not in text


def test_extract_text_pdf_cjk() -> None:
    """PDF text extraction must return real characters, not font-code mojibake.

    Exercises the PyMuPDF path. When a CJK font is available on the host
    (macOS Arial Unicode), embed it to verify CJK round-trips; otherwise fall
    back to Latin text to keep the test portable on CI.
    """
    import os

    import fitz

    cjk_font = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    use_cjk = os.path.exists(cjk_font)

    doc = fitz.open()
    page = doc.new_page()
    if use_cjk:
        page.insert_font(fontname="cjk", fontfile=cjk_font)
        page.insert_textbox(
            page.rect, "张三 后端架构师 订单中台重构", fontsize=12, fontname="cjk"
        )
    else:
        page.insert_text((72, 72), "Zhang San Backend Architect", fontsize=12)
    content = doc.tobytes()
    doc.close()

    text = extract_text(content, "application/pdf")
    assert text.strip()
    if use_cjk:
        assert "张三" in text
        assert "订单中台重构" in text
    else:
        assert "Zhang San" in text


def test_extract_text_empty_raises() -> None:
    with pytest.raises(ResumeExtractError):
        extract_text(b"   ", "text/plain")


def test_extract_text_unsupported_type() -> None:
    with pytest.raises(ResumeExtractError):
        extract_text(b"abc", "application/octet-stream")


# --- heuristic parser (no-LLM fallback) ---


def test_heuristic_parse_structures_resume() -> None:
    """Heuristic parser must split sections + extract basics, not blob text."""
    from gotit.core.resume.heuristic import heuristic_parse

    text = (
        "周馨睿\n"
        "(+86)195-1794-1774 | zhouxinrui02@gmail.com | AI应用研发工程师| 杭州\n"
        "工作经历\n"
        "阿里巴巴·淘天集团·AI 创新产品|AI应用研发工程师｜杭州\n"
        "2024.07—至今\n"
        "• 负责猫超商品域发品、素材库等核心页面前端研发。\n"
        "项目经历\n"
        "KnowMind Agent 应用平台|核心开发·Agent Runtime\n"
        "2026.01—至今\n"
        "技术栈：Claude Agent SDK · Redis · MySQL\n"
        "• 长对话稳定与多轮会话治理，reconnect 补发成功率≥95%。\n"
        "教育经历\n"
        "东北林业大学|软件工程｜工学学士\n"
        "2020.09—2024.06\n"
    )
    out = heuristic_parse(upload_id="x", resume_text=text)
    doc = out.document
    assert doc.basics.name == "周馨睿"
    assert doc.basics.target_role == "AI应用研发工程师"
    # Only the 项目经历 section maps to projects; 工作经历 is excluded.
    names = [p.name for p in doc.projects]
    assert "KnowMind Agent 应用平台" in names
    assert "阿里巴巴·淘天集团·AI 创新产品" not in names  # work exp, not a project
    assert "东北林业大学" not in names  # education, not a project
    km = next(p for p in doc.projects if p.name == "KnowMind Agent 应用平台")
    assert km.role == "核心开发·Agent Runtime"
    assert "Claude Agent SDK" in km.tech_stack
    assert "reconnect" in km.description


def test_heuristic_parse_fallback_placeholder() -> None:
    """Unstructured text with no sections → single placeholder project."""
    from gotit.core.resume.heuristic import heuristic_parse

    out = heuristic_parse(
        upload_id="x", resume_text="just some free-form bio text\nwith no headers"
    )
    assert len(out.document.projects) == 1
    assert out.document.projects[0].name == "占位项目"


def test_heuristic_parse_work_only_falls_back_to_work() -> None:
    """Resume with no 项目经历 section → work-experience entries used as projects."""
    from gotit.core.resume.heuristic import heuristic_parse

    text = (
        "张三\n13800000000 | zs@x.com | 后端工程师| 北京\n"
        "工作经历\n"
        "某公司|后端工程师｜北京\n"
        "2020.01—至今\n"
        "• 负责订单系统研发。\n"
    )
    out = heuristic_parse(upload_id="x", resume_text=text)
    names = [p.name for p in out.document.projects]
    assert "某公司" in names  # work entry used as project fallback


# --- e2e: apply (clear-rebuild) via API ---


@pytest.mark.asyncio
async def test_apply_resume_clear_rebuild(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    from uuid import uuid4

    from gotit.core.models import ResumeBasics, ResumeDocument, ResumeProject

    doc1 = ResumeDocument(
        basics=ResumeBasics(name="张三", target_role="后端架构师"),
        projects=[
            ResumeProject(name="订单中台", role="后端负责人", tech_stack=["Go", "Kafka"],
                          description="订单中台重构，QPS 800→12000。"),
        ],
    )
    upload_id = uuid4()

    # First apply: 1 project + 1 resume note, no claims.
    r = await client.post(
        "/v1/resumes/apply",
        headers=auth_headers,
        json={
            "upload_id": str(upload_id),
            "file_path": f"uploads/{upload_id}.pdf",
            "document": doc1.model_dump(mode="json"),
            "ingest": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["projects"]) == 1
    assert len(body["notes"]) == 1
    assert body["claims"] == []

    # Resume record exists.
    r = await client.get("/v1/resumes", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["document"]["basics"]["name"] == "张三"

    # A hand-written note under the project (learning data).
    r = await client.post(
        "/v1/days/2026-07-28/notes",
        headers=auth_headers,
        json={"body": "我的手写笔记", "title": "手写", "tags": ["manual"]},
    )
    handwritten_id = r.json()["id"]
    # Attach it to the project via... (no direct attach endpoint; just ensure it exists)

    # Second apply with a different project set: clear-rebuild.
    doc2 = ResumeDocument(
        basics=ResumeBasics(name="张三", target_role="后端架构师"),
        projects=[
            ResumeProject(name="风控引擎", role="核心开发", tech_stack=["Python", "Flink"],
                          description="实时风控流，准确率 98%。"),
        ],
    )
    r = await client.post(
        "/v1/resumes/apply",
        headers=auth_headers,
        json={
            "upload_id": str(uuid4()),
            "file_path": "uploads/replace.pdf",
            "document": doc2.model_dump(mode="json"),
            "ingest": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["projects"]) == 1
    assert body["projects"][0]["name"] == "风控引擎"

    # Old project gone, new project present.
    r = await client.get("/v1/projects", headers=auth_headers)
    names = {p["name"] for p in r.json()}
    assert names == {"风控引擎"}

    # Resume note replaced (only 1 resume note now, for 风控引擎).
    r = await client.get("/v1/days/2026-07-28/notes", headers=auth_headers)
    resume_notes = [n for n in r.json() if "resume" in (n.get("tags") or [])]
    assert len(resume_notes) == 1
    assert resume_notes[0]["title"] == "风控引擎"

    # Hand-written note still exists (learning data preserved).
    r = await client.get(f"/v1/notes/{handwritten_id}", headers=auth_headers)
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_resume_file_endpoint_serves_original(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    from uuid import uuid4

    from gotit.core.models import ResumeBasics, ResumeDocument, ResumeProject

    upload_id = uuid4()
    file_path = Path(f"uploads/{upload_id}.txt")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("我的简历原文：事件驱动架构", encoding="utf-8")
    try:
        doc = ResumeDocument(
            basics=ResumeBasics(name="李四", target_role="架构师"),
            projects=[
                ResumeProject(name="P", role="负责人", tech_stack=[], description="d"),
            ],
        )
        r = await client.post(
            "/v1/resumes/apply",
            headers=auth_headers,
            json={
                "upload_id": str(upload_id),
                "file_path": str(file_path),
                "document": doc.model_dump(mode="json"),
                "ingest": False,
            },
        )
        assert r.status_code == 200

        # Stored file_path includes the extension.
        r = await client.get("/v1/resumes", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["file_path"] == str(file_path)

        # File endpoint serves the original bytes with txt media type.
        r = await client.get("/v1/resumes/file", headers=auth_headers)
        assert r.status_code == 200
        assert "text/plain" in r.headers.get("content-type", "")
        assert "事件驱动架构" in r.text
    finally:
        file_path.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_resume_file_endpoint_no_resume(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.get("/v1/resumes/file", headers=auth_headers)
    assert r.status_code == 404
