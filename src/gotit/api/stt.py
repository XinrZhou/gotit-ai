"""Speech-to-text adapter for voice teach-back.

Uses ``STT_*`` when set, else falls back to ``LLM_*`` (OpenAI-compatible
``/audio/transcriptions``). When neither key is present, STT is unavailable
and callers should keep the text-only teach path.
"""

from __future__ import annotations

from gotit.api.settings import Settings


class SttUnavailable(Exception):
    """Raised when no STT/LLM key is configured or stub is off."""


def stt_available(settings: Settings) -> bool:
    """True when recording/upload transcription can be attempted."""
    if settings.stt_stub:
        return True
    return bool(settings.stt_api_key or settings.llm_api_key)


def _stt_binding(settings: Settings) -> tuple[str, str, str]:
    """Return (api_key, base_url, model) for the transcription call."""
    key = (settings.stt_api_key or settings.llm_api_key).strip()
    base = (settings.stt_base_url or settings.llm_base_url).rstrip("/")
    model = (settings.stt_model or "whisper-1").strip() or "whisper-1"
    return key, base, model


async def transcribe_audio(
    data: bytes,
    *,
    filename: str,
    content_type: str | None,
    settings: Settings,
) -> str:
    """Transcribe audio bytes → text. Stub path for tests / no network."""
    if not stt_available(settings):
        raise SttUnavailable("STT not configured; use text teach-back")

    if settings.stt_stub:
        stub = (settings.stt_stub_text or "").strip()
        return stub or "[stub transcript]"

    key, base, model = _stt_binding(settings)
    if not key:
        raise SttUnavailable("STT not configured; use text teach-back")

    import httpx

    name = filename or "audio.webm"
    mime = content_type or "application/octet-stream"
    url = f"{base}/audio/transcriptions"
    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            files={"file": (name, data, mime)},
            data={"model": model},
        )
    if res.status_code >= 400:
        raise RuntimeError(f"STT failed ({res.status_code}): {res.text[:400]}")
    body = res.json()
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("STT returned empty transcript")
    return text.strip()
