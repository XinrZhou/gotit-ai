"""Voice / text teach-back → shared Critic + gate finalize."""

from __future__ import annotations

from datetime import date

import pytest
from httpx import AsyncClient

from gotit.core.teach_verify import teach_examine_verdict


def test_teach_examine_verdict_mapping() -> None:
    assert teach_examine_verdict(True) == "passed"
    assert teach_examine_verdict(False) == "owe_next"


@pytest.mark.asyncio
async def test_teach_text_path_claim_finalize(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = date.today().isoformat()
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "QKV projects queries against keys.", "title": "attn"},
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

    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={
            "topic": "注意力",
            "answer": "Query 去对 Key，Value 加权求和。",
            "claim_id": claim_id,
            "you_taught_well": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"]["done"] is True
    assert body["verdict"]["you_taught_well"] is True
    assert body["verify"]["examine_verdict"] == "passed"
    assert body["verify"]["recheck_verdict"] == "passed"
    assert body["verify"]["gate_verdict"] == "passed"
    assert body["writeback"]["claim"]["status"] == "mastered"


@pytest.mark.asyncio
async def test_teach_owe_next_writes_failure_digest(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    day = date.today().isoformat()
    r = await client.post(
        f"/v1/days/{day}/notes",
        headers=auth_headers,
        json={"body": "Masking hides future tokens.", "title": "mask"},
    )
    note_id = r.json()["id"]
    r = await client.post(
        f"/v1/notes/{note_id}/ingest",
        headers=auth_headers,
        json={"add_plan_item": True},
    )
    claim_id = r.json()["claims"][0]["id"]

    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={
            "topic": "mask",
            "answer": "不太清楚。",
            "claim_id": claim_id,
            "you_taught_well": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verify"]["gate_verdict"] == "owe_next"
    assert body["writeback"].get("failure_digest_id")


@pytest.mark.asyncio
async def test_teach_capabilities_and_transcribe_stub(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from gotit.api import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("STT_STUB", "true")
    monkeypatch.setenv("STT_STUB_TEXT", "这是转写稿")
    settings_mod.get_settings.cache_clear()

    r = await client.get("/v1/teach/capabilities", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["stt_available"] is True

    r = await client.post(
        "/v1/teach/transcribe",
        headers=auth_headers,
        files={"file": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert r.status_code == 200
    assert r.json()["transcript"] == "这是转写稿"

    settings_mod.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_teach_transcribe_unavailable_without_key(
    client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from gotit.api import settings as settings_mod

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("STT_STUB", "false")
    monkeypatch.setenv("STT_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "")
    settings_mod.get_settings.cache_clear()

    r = await client.get("/v1/teach/capabilities", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["stt_available"] is False

    r = await client.post(
        "/v1/teach/transcribe",
        headers=auth_headers,
        files={"file": ("clip.webm", b"x", "audio/webm")},
    )
    assert r.status_code == 503

    settings_mod.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_teach_without_claim_skips_finalize(
    client: AsyncClient, auth_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/v1/teach",
        headers=auth_headers,
        json={"topic": "自由主题", "you_taught_well": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["verdict"]["you_taught_well"] is True
    assert "verify" not in body
    assert "writeback" not in body
