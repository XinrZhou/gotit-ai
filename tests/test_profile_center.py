"""Profile center: skills catalog + MCP connectors."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_skills_catalog_and_install(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.get("/v1/skills", headers=auth_headers)
    assert r.status_code == 200
    names = {s["name"] for s in r.json()}
    assert "debug" in names
    assert "review" in names
    for s in r.json():
        assert s["enabled"] is True

    md = """---
skill: custom-focus
notes: focus mode for deep work
---

## Skill: Focus

Stay on one claim. No tangents.
"""
    r = await client.post(
        "/v1/skills",
        headers=auth_headers,
        json={"markdown": md},
    )
    assert r.status_code == 200
    assert r.json()["name"] == "custom-focus"
    assert r.json()["source"] == "user"

    r = await client.get("/v1/skills", headers=auth_headers)
    by_name = {s["name"]: s for s in r.json()}
    assert by_name["custom-focus"]["enabled"] is True

    r = await client.patch(
        "/v1/skills/custom-focus",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = await client.patch(
        "/v1/skills/debug",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = await client.get("/v1/skills", headers=auth_headers)
    by_name = {s["name"]: s for s in r.json()}
    assert by_name["debug"]["enabled"] is False
    assert by_name["custom-focus"]["enabled"] is False

    r = await client.delete("/v1/skills/custom-focus", headers=auth_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_skill_get_and_update(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    md = """---
skill: editable-skill
notes: v1
---

## Body v1
"""
    r = await client.post("/v1/skills", headers=auth_headers, json={"markdown": md})
    assert r.status_code == 200

    r = await client.get("/v1/skills/editable-skill", headers=auth_headers)
    assert r.status_code == 200
    detail = r.json()
    assert detail["editable"] is True
    assert "Body v1" in detail["markdown"]

    md2 = """---
skill: editable-skill
notes: v2
---

## Body v2
"""
    r = await client.patch(
        "/v1/skills/editable-skill",
        headers=auth_headers,
        json={"markdown": md2},
    )
    assert r.status_code == 200
    assert r.json()["notes"] == "v2"

    r = await client.get("/v1/skills/editable-skill", headers=auth_headers)
    assert "Body v2" in r.json()["markdown"]

    r = await client.get("/v1/skills/debug", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["editable"] is False

    r = await client.delete("/v1/skills/editable-skill", headers=auth_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_chat_skills_respect_catalog(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/v1/identities/seed", headers=auth_headers)
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


@pytest.mark.asyncio
async def test_connectors_crud_and_import(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/connectors",
        headers=auth_headers,
        json={
            "name": "demo-http",
            "transport": "http",
            "config": {"url": "http://127.0.0.1:9/mcp", "headers": {}},
            "enabled": True,
        },
    )
    assert r.status_code == 200
    conn = r.json()
    assert conn["name"] == "demo-http"
    assert conn["last_status"] == "unknown"
    cid = conn["id"]

    r = await client.get("/v1/connectors", headers=auth_headers)
    assert r.status_code == 200
    assert any(c["id"] == cid for c in r.json())

    r = await client.patch(
        f"/v1/connectors/{cid}",
        headers=auth_headers,
        json={"enabled": False},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is False

    r = await client.post(
        "/v1/connectors/import",
        headers=auth_headers,
        json={
            "config": {
                "mcpServers": {
                    "local-echo": {
                        "command": "python",
                        "args": ["-c", "print('hi')"],
                        "env": {"FOO": "1"},
                    }
                }
            }
        },
    )
    assert r.status_code == 200
    names = {c["name"] for c in r.json()}
    assert "local-echo" in names

    r = await client.delete(f"/v1/connectors/{cid}", headers=auth_headers)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_connector_bad_config(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/connectors",
        headers=auth_headers,
        json={"name": "bad", "transport": "stdio", "config": {}},
    )
    assert r.status_code == 400
