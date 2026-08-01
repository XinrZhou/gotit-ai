"""Thread delete + first-message title derivation."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from gotit.db.ops.thread import (
    PLACEHOLDER_THREAD_TITLES,
    derive_thread_title,
)


def test_derive_thread_title_truncates() -> None:
    assert derive_thread_title("你好") == "你好"
    assert derive_thread_title("") == "新对话"
    long = "这是一句很长很长的开场白用来测试标题截断行为是否符合预期啊"
    title = derive_thread_title(long, max_len=28)
    assert title.endswith("…")
    assert len(title) == 28
    assert title.startswith("这是一句")


def test_placeholder_thread_titles() -> None:
    assert "新对话" in PLACEHOLDER_THREAD_TITLES
    assert "学习会话" in PLACEHOLDER_THREAD_TITLES


@pytest.mark.asyncio
async def test_patch_thread_title(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    created = await client.post(
        "/v1/threads", headers=auth_headers, json={"kind": "chat"}
    )
    assert created.status_code == 200
    tid = created.json()["id"]
    patched = await client.patch(
        f"/v1/threads/{tid}",
        headers=auth_headers,
        json={"title": "Function calling 最佳实践"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "Function calling 最佳实践"


@pytest.mark.asyncio
async def test_delete_thread_and_auto_title(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    await client.post("/v1/identities/seed", headers=auth_headers)

    created = await client.post(
        "/v1/threads", headers=auth_headers, json={"kind": "chat"}
    )
    assert created.status_code == 200
    thread = created.json()
    assert thread["title"] == "新对话"
    tid = thread["id"]

    reply = await client.post(
        f"/v1/threads/{tid}/messages",
        headers=auth_headers,
        json={"text": "帮我梳理一下 Redis 缓存穿透", "mentions": ["compass"]},
    )
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["thread"] is not None
    assert body["thread"]["title"].startswith("帮我梳理一下")
    assert body["agent_messages"]
    # thinking is optional (stub / some gateways omit it); title + delete are the spine
    meta = body["agent_messages"][0].get("metadata") or {}
    assert isinstance(meta, dict)

    deleted = await client.delete(f"/v1/threads/{tid}", headers=auth_headers)
    assert deleted.status_code == 200
    listed = await client.get("/v1/threads", headers=auth_headers)
    assert listed.status_code == 200
    assert all(t["id"] != tid for t in listed.json())
