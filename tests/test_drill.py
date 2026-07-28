"""End-to-end tests for drill materials + resume-driven drill sessions."""
from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from gotit.core.models import ResumeBasics, ResumeDocument, ResumeProject


async def _seed_resume(client: AsyncClient, headers: dict[str, str]) -> None:
    doc = ResumeDocument(
        basics=ResumeBasics(name="张三", target_role="后端架构师"),
        projects=[
            ResumeProject(
                name="订单中台",
                role="后端负责人",
                tech_stack=["Go", "Kafka"],
                description="订单中台重构，QPS 800→12000。",
            )
        ],
    )
    r = await client.post(
        "/v1/resumes/apply",
        headers=headers,
        json={
            "upload_id": str(uuid4()),
            "file_path": "uploads/test-resume.pdf",
            "document": doc.model_dump(mode="json"),
            "ingest": False,
        },
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_drill_materials_crud(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    # Create
    r = await client.post(
        "/v1/drill/materials",
        headers=auth_headers,
        json={"title": "订单中台深挖要点", "body": "事件驱动 vs 同步调用；Kafka 分区策略。"},
    )
    assert r.status_code == 200
    mat = r.json()
    mid = mat["id"]
    assert mat["title"] == "订单中台深挖要点"

    # List
    r = await client.get("/v1/drill/materials", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Update via PATCH
    r = await client.patch(
        f"/v1/drill/materials/{mid}",
        headers=auth_headers,
        json={"title": "订单中台深挖要点 v2", "body": "更新内容"},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "订单中台深挖要点 v2"

    # Delete
    r = await client.delete(f"/v1/drill/materials/{mid}", headers=auth_headers)
    assert r.status_code == 200
    r = await client.get("/v1/drill/materials", headers=auth_headers)
    assert r.json() == []


@pytest.mark.asyncio
async def test_drill_material_upload_txt(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    payload = "事件驱动 vs 同步调用\nKafka 分区策略".encode()
    r = await client.post(
        "/v1/drill/materials/upload",
        headers=auth_headers,
        files={"file": ("订单笔记.txt", payload, "text/plain")},
    )
    assert r.status_code == 200
    out = r.json()
    assert out["title"] == "订单笔记"
    assert "事件驱动" in out["body"]


@pytest.mark.asyncio
async def test_drill_material_upload_unsupported_type(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/drill/materials/upload",
        headers=auth_headers,
        files={"file": ("x.bin", b"\x00\x01", "application/octet-stream")},
    )
    assert r.status_code == 415


@pytest.mark.asyncio
async def test_drill_material_upload_then_save(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Upload returns a preview; client then saves it via the upsert endpoint."""
    r = await client.post(
        "/v1/drill/materials/upload",
        headers=auth_headers,
        files={"file": ("架构要点.md", "# 架构\n事件驱动取舍".encode(), "text/markdown")},
    )
    assert r.status_code == 200
    preview = r.json()
    assert preview["title"] == "架构要点"
    r = await client.post(
        "/v1/drill/materials",
        headers=auth_headers,
        json={"title": preview["title"], "body": preview["body"]},
    )
    assert r.status_code == 200
    assert r.json()["title"] == "架构要点"


@pytest.mark.asyncio
async def test_drill_session_e2e(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await _seed_resume(client, auth_headers)

    # Add a material to be consumed.
    r = await client.post(
        "/v1/drill/materials",
        headers=auth_headers,
        json={"title": "资料", "body": "偏架构：事件驱动取舍。"},
    )
    assert r.status_code == 200

    # Start a session (stub bypass, no LLM key): round=tech_2, direction=偏架构.
    r = await client.post(
        "/v1/drill/sessions",
        headers=auth_headers,
        json={"round": "tech_2", "direction": "偏架构"},
    )
    assert r.status_code == 200
    body = r.json()
    session = body["session"]
    verdict = body["verdict"]
    assert session["round"] == "tech_2"
    assert session["direction"] == "偏架构"
    assert verdict["done"] is False
    assert verdict["follow_up"]
    assert verdict["round"] == "tech_2"
    session_id = session["id"]

    # List sessions
    r = await client.get("/v1/drill/sessions", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Continue with an answer -> stub wraps up (done=true).
    r = await client.post(
        f"/v1/drill/sessions/{session_id}",
        headers=auth_headers,
        json={"answer": "我用了 Kafka 做事件总线，分区按订单ID。"},
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is True
    assert v["follow_up"] is None

    # Session is now done; continuing again is rejected.
    r = await client.post(
        f"/v1/drill/sessions/{session_id}",
        headers=auth_headers,
        json={"answer": "再答一次"},
    )
    assert r.status_code == 409

    # Get session shows messages persisted.
    r = await client.get(f"/v1/drill/sessions/{session_id}", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()["messages"]
    assert len(msgs) >= 2
    roles = [m["role"] for m in msgs]
    assert "examiner" in roles and "user" in roles


@pytest.mark.asyncio
async def test_drill_session_requires_resume(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/drill/sessions",
        headers=auth_headers,
        json={"round": "tech_1"},
    )
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_drill_session_project_focus(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await _seed_resume(client, auth_headers)
    r = await client.get("/v1/projects", headers=auth_headers)
    project_id = r.json()[0]["id"]

    r = await client.post(
        "/v1/drill/sessions",
        headers=auth_headers,
        json={"round": "hr", "project_id": project_id},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["project_id"] == project_id
    assert body["session"]["round"] == "hr"
    # HR stub opening line is behavioral.
    assert "介绍下你自己" in body["verdict"]["follow_up"]
