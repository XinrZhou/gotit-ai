"""End-to-end demo: full agent-rewrite flow against the API (stub paths).

Covers: prompt registration → note + ingest (Compass stub) → examine verdict
bypass (Axiom writeback) → curate → memory → prompt observation.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_e2e_agent_rewrite_flow(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    day = "2026-07-28"

    # 1. Register prompts from prompts/*.md
    r = await client.post("/v1/prompts/register", headers=auth_headers)
    assert r.status_code == 200
    registered = r.json()
    agents = {v["agent_name"] for v in registered}
    assert {"axiom", "compass", "echo"}.issubset(agents)

    # 2. Add a note and ingest (Compass stub fallback, no LLM key)
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={
            "body": "False fluency is recognizing without explaining.",
            "title": "ff",
            "tags": ["learning"],
        },
    )
    assert r.status_code == 200
    note_id = r.json()["id"]

    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    assert r.status_code == 200
    claim_id = r.json()["claims"][0]["id"]

    # 3. Examine with continuous verdicts (bypass agent)
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"claim_id": claim_id, "verdict": "almost"},
    )
    assert r.status_code == 200
    assert r.json()["writeback"]["claim"]["status"] == "in_progress"

    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"claim_id": claim_id, "verdict": "passed"},
    )
    assert r.json()["writeback"]["claim"]["status"] == "mastered"

    # 4. Curate (add a recommended claim to the plan)
    r = await client.post(
        "/v1/curate",
        headers=auth_headers,
        json={"day": day, "claim_texts": ["False fluency is recognizing without explaining."]},
    )
    assert r.status_code == 200
    assert isinstance(r.json()["items"], list)

    # 5. Echo teach-back (bypass)
    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={"topic": "false fluency", "you_taught_well": True},
    )
    assert r.status_code == 200
    assert r.json()["verdict"]["done"] is True

    # 6. Memory: add + list
    r = await client.post(
        "/v1/memory",
        headers=auth_headers,
        json={
            "layer": "working",
            "kind": "weakness",
            "content": {"k": "v"},
            "topic": "false-fluency",
        },
    )
    assert r.status_code == 200
    mem_id = r.json()["id"]
    r = await client.get("/v1/memory?layer=working", headers=auth_headers)
    assert any(m["id"] == mem_id for m in r.json())

    # 7. Prompt observation
    r = await client.get("/v1/prompts?active_only=true", headers=auth_headers)
    assert r.status_code == 200
    active = r.json()
    assert len(active) >= 3
    assert all(v["is_active"] for v in active)

    # 8. Resume-driven drill: apply a resume (clear-rebuild projects), add a
    #    note under a project, ingest, then run a drill session (stub).
    from uuid import uuid4

    from gotit.core.models import ResumeBasics, ResumeDocument, ResumeProject

    resume_doc = ResumeDocument(
        basics=ResumeBasics(name="张三", target_role="后端架构师"),
        projects=[
            ResumeProject(
                name="订单服务",
                role="后端主程",
                goal="扛住 3 轮深挖",
                tech_stack=["Go", "MySQL", "Redis"],
                description="订单服务，分库分表扛写入峰值。",
            )
        ],
    )
    r = await client.post(
        "/v1/resumes/apply",
        headers=auth_headers,
        json={
            "upload_id": str(uuid4()),
            "document": resume_doc.model_dump(mode="json"),
            "ingest": False,
        },
    )
    assert r.status_code == 200
    project_id = r.json()["projects"][0]["id"]

    r = await client.get("/v1/projects", headers=auth_headers)
    assert any(p["id"] == project_id for p in r.json())

    # note under project -> claim inherits project_id
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={
            "body": "我们用分库分表扛住订单写入峰值。",
            "title": "分库分表",
            "project_id": project_id,
        },
    )
    assert r.status_code == 200
    proj_note_id = r.json()["id"]
    assert r.json()["project_id"] == project_id

    r = await client.post(
        f"/v1/notes/{proj_note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    assert r.status_code == 200
    assert r.json()["claims"][0]["project_id"] == project_id

    # project progress
    r = await client.get(
        f"/v1/projects/{project_id}/progress", headers=auth_headers
    )
    assert r.status_code == 200
    assert r.json()["claims_total"] >= 1

    # drill session: start (stub: opening question), then continue (stub: wrap up)
    r = await client.post(
        "/v1/drill/sessions",
        headers=auth_headers,
        json={"round": "tech_2", "project_id": project_id},
    )
    assert r.status_code == 200
    assert r.json()["verdict"]["done"] is False
    assert r.json()["verdict"]["follow_up"]
    session_id = r.json()["session"]["id"]

    r = await client.post(
        f"/v1/drill/sessions/{session_id}",
        headers=auth_headers,
        json={"answer": "我用了 ShardingSphere 按订单 ID 分库。"},
    )
    assert r.status_code == 200
    assert r.json()["verdict"]["done"] is True

    # update + archive
    r = await client.patch(
        f"/v1/projects/{project_id}",
        headers=auth_headers,
        json={"goal": "扛住 5 轮深挖"},
    )
    assert r.status_code == 200
    assert r.json()["goal"] == "扛住 5 轮深挖"

    r = await client.patch(
        f"/v1/projects/{project_id}",
        headers=auth_headers,
        json={"status": "archived"},
    )
    assert r.json()["status"] == "archived"


@pytest.mark.asyncio
async def test_e2e_topic_session_examine(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Topic-session mode: Axiom shuttles across the topic's claims (stub path)."""
    from datetime import date
    from uuid import uuid4

    from gotit.core.models import MasteryStatus
    from gotit.db import ops as day_ops
    from gotit.db import session_scope
    from gotit.db.models import ClaimRow

    today = date.today()
    topic = "提示词工程"

    # Seed two claims under `topic` plus today's plan items linking to them.
    async with session_scope() as session:
        await day_ops.ensure_day(session, today, user_id="local")
        claim_ids: list[str] = []
        for text in ["上下文预算的取舍", "few-shot 的边界"]:
            cid = uuid4()
            session.add(
                ClaimRow(
                    id=cid,
                    user_id="local",
                    text=text,
                    source_excerpt=text[:200],
                    status=MasteryStatus.NOT_YET.value,
                    source_note_id=None,
                    next_review_at=None,
                    topic=topic,
                    tags=[],
                    project_id=None,
                )
            )
            await day_ops.upsert_plan_item(
                session,
                today,
                title=text,
                user_id="local",
                claim_id=cid,
            )
            claim_ids.append(str(cid))

    # First turn: opening question for the first claim, not done.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"topic": topic},
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is False
    assert v["verdict"] is None
    assert v["current_claim_id"] == claim_ids[0]
    assert v["follow_up"]
    assert v["session_done"] is False
    assert r.json()["writeback"] is None

    # Second turn: answer -> judge first claim passed, advance to second.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={
            "topic": topic,
            "answer": "上下文预算要留给模型推理，prompt 越短越好。",
            "history": [{"role": "examiner", "text": v["follow_up"]}],
        },
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is True
    assert v["verdict"] == "passed"
    assert v["current_claim_id"] == claim_ids[0]
    assert v["session_done"] is False
    wb = r.json()["writeback"]
    assert wb["claim"]["status"] == "mastered"

    # Third turn: answer -> judge second claim passed, session done.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={
            "topic": topic,
            "answer": "few-shot 超过 5 例收益递减。",
            "history": [
                {"role": "examiner", "text": "q1"},
                {"role": "user", "text": "a1"},
                {"role": "examiner", "text": "q2"},
            ],
        },
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is True
    assert v["verdict"] == "passed"
    assert v["current_claim_id"] == claim_ids[1]
    assert v["session_done"] is True

    # Empty topic -> session done immediately.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={"topic": "不存在主题"},
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["session_done"] is True
    assert v["current_claim_id"] is None


@pytest.mark.asyncio
async def test_e2e_note_session_examine(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Note-session mode: Axiom shuttles across a note's claims (stub path)."""
    from datetime import date
    from uuid import uuid4

    from gotit.core.models import MasteryStatus
    from gotit.db import ops as day_ops
    from gotit.db import session_scope
    from gotit.db.models import ClaimRow, DayNoteRow

    today = date.today()
    note_id = uuid4()

    async with session_scope() as session:
        await day_ops.ensure_day(session, today, user_id="local")
        note_view = await day_ops.add_note(
            session, today, "提示词工程笔记内容", title="提示词工程笔记", user_id="local"
        )
        note_id = note_view.id
        claim_ids: list[str] = []
        for text in ["上下文预算的取舍", "few-shot 的边界"]:
            cid = uuid4()
            session.add(
                ClaimRow(
                    id=cid,
                    user_id="local",
                    text=text,
                    source_excerpt=text[:200],
                    status=MasteryStatus.NOT_YET.value,
                    source_note_id=note_id,
                    next_review_at=None,
                    topic=None,
                    tags=[],
                    project_id=None,
                )
            )
            claim_ids.append(str(cid))
        # Mirror ingest_note: record claim ids on the note (extraction order).
        note_row = await session.get(DayNoteRow, note_id)
        note_row.claim_ids = list(claim_ids)

    # First turn: opening question for the first claim.
    r = await client.post(
        "/v1/examine", headers=auth_headers, json={"note_id": str(note_id)}
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is False
    assert v["current_claim_id"] == claim_ids[0]
    assert v["session_done"] is False

    # Second turn: answer -> judge first claim passed, advance.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={
            "note_id": str(note_id),
            "answer": "上下文预算要留给模型推理。",
            "history": [{"role": "examiner", "text": v["follow_up"]}],
        },
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is True
    assert v["verdict"] == "passed"
    assert v["current_claim_id"] == claim_ids[0]
    assert v["session_done"] is False

    # Third turn: judge second claim, session done.
    r = await client.post(
        "/v1/examine",
        headers=auth_headers,
        json={
            "note_id": str(note_id),
            "answer": "few-shot 超过 5 例收益递减。",
            "history": [
                {"role": "examiner", "text": "q1"},
                {"role": "user", "text": "a1"},
                {"role": "examiner", "text": "q2"},
            ],
        },
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["done"] is True
    assert v["verdict"] == "passed"
    assert v["current_claim_id"] == claim_ids[1]
    assert v["session_done"] is True

    # Empty note -> session done immediately.
    async with session_scope() as session:
        empty_view = await day_ops.add_note(
            session, today, "空", title="空笔记", user_id="local"
        )
    r = await client.post(
        "/v1/examine", headers=auth_headers, json={"note_id": str(empty_view.id)}
    )
    assert r.status_code == 200
    v = r.json()["verdict"]
    assert v["session_done"] is True
    assert v["current_claim_id"] is None


@pytest.mark.asyncio
async def test_e2e_list_all_notes(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    """GET /v1/notes returns notes across days, each with a `day` label."""
    from datetime import date

    from gotit.db import ops as day_ops
    from gotit.db import session_scope

    async with session_scope() as session:
        await day_ops.add_note(
            session, date(2026, 7, 25), "d25 body", title="d25", user_id="local"
        )
        await day_ops.add_note(
            session, date(2026, 7, 28), "d28 body", title="d28", user_id="local"
        )

    r = await client.get("/v1/notes", headers=auth_headers)
    assert r.status_code == 200
    notes = r.json()
    titles = {n["title"] for n in notes}
    assert {"d25", "d28"}.issubset(titles)
    by_title = {n["title"]: n for n in notes}
    assert by_title["d25"]["day"] == "2026-07-25"
    assert by_title["d28"]["day"] == "2026-07-28"
