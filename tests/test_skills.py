"""P4: skills on-demand loading."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from gotit.core.skills import list_skills, load_skill


def test_skills_list_and_load() -> None:
    names = list_skills()
    assert "debug" in names
    assert "review" in names

    body = load_skill("debug")
    assert body is not None
    assert "minimal repro" in body.lower() or "bisect" in body.lower()

    assert load_skill("does-not-exist") is None


@pytest.mark.asyncio
async def test_chat_accepts_skills(client: AsyncClient, auth_headers: dict[str, str]) -> None:
    await client.post("/v1/identities/seed", headers=auth_headers)

    # list skills via REST
    r = await client.get("/v1/skills", headers=auth_headers)
    assert r.status_code == 200
    assert "debug" in r.json()

    # create a thread and post a message requesting a skill (stub path: no LLM,
    # but the route must accept the `skills` field without erroring)
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "skill thread", "kind": "chat"},
    )
    tid = r.json()["id"]
    r = await client.post(
        f"/v1/threads/{tid}/messages",
        headers=auth_headers,
        json={"text": "帮我调一个 bug", "mentions": [], "skills": ["debug"]},
    )
    assert r.status_code == 200
    assert r.json()["agent_messages"][0]["role"] == "agent"
