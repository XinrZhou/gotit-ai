"""Chat LLM failures surface as in-thread agent replies (no 502 roll-back)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from gotit.api.deps import get_model
from gotit.api.settings import get_settings


@pytest.mark.asyncio
async def test_llm_failure_returns_agent_error_bubble(
    client: AsyncClient,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_API_KEY", "fake-key-for-test")
    get_settings.cache_clear()
    get_model.cache_clear()

    async def _boom(*_a: object, **_k: object) -> None:
        raise ConnectionError("upstream down")

    monkeypatch.setattr("gotit.api.chat_orchestrator.run_chat", _boom)

    await client.post("/v1/identities/seed", headers=auth_headers)
    r = await client.post(
        "/v1/threads",
        headers=auth_headers,
        json={"title": "fail-path", "kind": "chat"},
    )
    assert r.status_code == 200
    thread_id = r.json()["id"]

    r = await client.post(
        f"/v1/threads/{thread_id}/messages",
        headers=auth_headers,
        json={"text": "介绍一下你自己", "mentions": ["axiom"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_message"]["text"] == "介绍一下你自己"
    assert len(body["agent_messages"]) == 1
    agent = body["agent_messages"][0]
    assert agent["agent_name"] == "axiom"
    assert agent["metadata"].get("error") is True
    assert "暂时没回上" in agent["text"]
    assert "ConnectionError" in agent["text"]

    # Persisted for reload — not rolled back with the transaction.
    r = await client.get(f"/v1/threads/{thread_id}/messages", headers=auth_headers)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["metadata"].get("error") is True

    get_settings.cache_clear()
    get_model.cache_clear()
