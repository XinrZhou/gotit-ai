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


def test_extract_text_empty_raises() -> None:
    with pytest.raises(ResumeExtractError):
        extract_text(b"   ", "text/plain")


def test_extract_text_unsupported_type() -> None:
    with pytest.raises(ResumeExtractError):
        extract_text(b"abc", "application/octet-stream")


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
        json={"upload_id": str(uuid4()), "document": doc2.model_dump(mode="json"), "ingest": False},
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
