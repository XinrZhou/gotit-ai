"""OpenClaw shell writeback + obs (profile / graph v0) over memory + claims."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import (
    Claim,
    DigestCronSyncResult,
    DigestFeed,
    DigestPrefs,
    GraphEdge,
    GraphNode,
    GraphView,
    InterestPromoteResult,
    MasteryStatus,
    MemoryEntry,
    ProfileTopicStat,
    ProfileView,
)
from gotit.db.models import ClaimRow, MemoryEntryRow, ProjectRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view
from gotit.db.ops.memory import add_memory, list_memory
from gotit.db.ops.note import _strip_html

KIND_SHELL_EVENT = "shell_event"
KIND_INTEREST = "interest"
KIND_TRAJECTORY = "trajectory"
KIND_DIGEST_PREFS = "digest_prefs"

# Promote quality: rule-first vacuous reject; max 3 claims per interest.
PROMOTE_MAX_CLAIMS = 3
_PROMOTE_MIN_LEN = 12
_PROMOTE_TZ = ZoneInfo("Asia/Shanghai")
_VACUOUS_EXACT = re.compile(
    r"^(太棒了|真棒|好看|有意思|有趣|不错|喜欢|爱了|赞|"
    r"amazing|interesting|cool|wow|nice|great|love\s*it|"
    r"今日要闻|今日热点|热门资讯)[!！.。…\s]*$",
    re.IGNORECASE,
)
_REWRITE_HINT = (
    "改写成可检验的短句，例如：「在条件 X 下，Y 会导致 Z」"
    "（含主体与可证伪结果）。"
)

DEFAULT_DIGEST_FEEDS: list[DigestFeed] = [
    DigestFeed(
        id="qbitai",
        label="量子位",
        url="https://www.qbitai.com/category/%E8%B5%84%E8%AE%AF/feed",
    ),
    DigestFeed(
        id="hf-blog",
        label="Hugging Face Blog",
        url="https://huggingface.co/blog/feed.xml",
    ),
    DigestFeed(
        id="openai-news",
        label="OpenAI News",
        url="https://openai.com/news/rss.xml",
    ),
    DigestFeed(
        id="deepmind",
        label="Google DeepMind",
        url="https://deepmind.google/blog/rss.xml",
    ),
    DigestFeed(
        id="marktechpost",
        label="MarkTechPost",
        url="https://www.marktechpost.com/feed/",
        enabled=False,
    ),
]


def default_digest_prefs() -> DigestPrefs:
    return DigestPrefs(feeds=list(DEFAULT_DIGEST_FEEDS))


def _prefs_from_content(content: dict[str, Any]) -> DigestPrefs:
    base = default_digest_prefs().model_dump(mode="json")
    base.update(content or {})
    return DigestPrefs.model_validate(base)


async def record_shell_event(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    job: str,
    items: list[dict[str, Any]] | None = None,
    due_summary: list[str] | None = None,
    errors: list[str] | None = None,
    delivery_ok: bool | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
    run_id: str | None = None,
    subject: str | None = None,
    day: str | None = None,
) -> MemoryEntry:
    """Persist a plan/news push as working-layer shell_event."""
    normalized: list[dict[str, Any]] = []
    for i, raw in enumerate(items or [], start=1):
        normalized.append(
            {
                "n": int(raw.get("n") or i),
                "title": str(raw.get("title") or "").strip(),
                "link": raw.get("link"),
                "feed_id": raw.get("feed_id"),
                "label": raw.get("label"),
            }
        )
    picks = [str(x).strip() for x in (due_summary or []) if str(x).strip()]
    sub = (subject or "").strip()
    if not sub:
        if picks:
            sub = picks[0]
        elif job == "news" and normalized and (normalized[0].get("title") or "").strip():
            # Plan jobs must never take subject from RSS items.
            sub = str(normalized[0]["title"]).strip()
    content: dict[str, Any] = {
        "job": job,
        "subject": sub or None,
        "day": (day or "").strip() or None,
        "items": normalized,
        "due_summary": picks,
        "errors": list(errors or []),
        "delivery_ok": delivery_ok,
    }
    source: dict[str, Any] = {
        "channel": channel,
        "skill": skill,
        "job": job,
    }
    if run_id:
        source["run_id"] = run_id
    return await add_memory(
        session,
        user_id=user_id,
        layer="working",
        kind=KIND_SHELL_EVENT,
        topic=f"digest:{job}",
        content=content,
        source=source,
    )


async def record_interest(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    event_id: UUID | str,
    item_index: int,
    title: str,
    link: str | None = None,
    feed_id: str | None = None,
    topic: str | None = None,
    channel: str = "openclaw-weixin",
    skill: str = "digest",
) -> MemoryEntry:
    """User said a digest item was useful — long-layer interest signal only."""
    eid = str(event_id)
    content: dict[str, Any] = {
        "event_id": eid,
        "item_index": item_index,
        "title": title.strip(),
        "link": link,
        "feed_id": feed_id,
    }
    return await add_memory(
        session,
        user_id=user_id,
        layer="long",
        kind=KIND_INTEREST,
        topic=topic,
        content=content,
        source={"channel": channel, "skill": skill, "event_id": eid},
    )


def claim_reject_reason(text: str) -> str | None:
    """Rule-first vacuous / untestable filter. Returns reason or None if ok."""
    plain = _strip_html(text).strip()
    if not plain:
        return "主张为空"
    if len(plain) < _PROMOTE_MIN_LEN:
        return "主张过短，无法检验"
    if _VACUOUS_EXACT.match(plain):
        return "纯情绪或空话，无法检验"
    # Require at least one letter / CJK ideograph (not only punctuation/digits).
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", plain):
        return "缺少可检验主体"
    return None


def interest_material(content: dict[str, Any]) -> str:
    """Context injected for extract — this interest item only."""
    title = _strip_html(str(content.get("title") or "")).strip()
    link = str(content.get("link") or "").strip()
    bits = [title] if title else []
    if link:
        bits.append(f"链接：{link}")
    return "\n".join(bits).strip()


def _candidate_texts_from_interest(
    content: dict[str, Any],
    *,
    claim_texts: list[str] | None = None,
) -> list[str]:
    if claim_texts:
        return [t.strip() for t in claim_texts if str(t).strip()][:PROMOTE_MAX_CLAIMS]
    title = _strip_html(str(content.get("title") or "")).strip()
    return [title] if title else []


async def promote_interest(
    session: AsyncSession,
    interest_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
    claims: list[Claim] | None = None,
    claim_texts: list[str] | None = None,
    day: date | None = None,
) -> InterestPromoteResult:
    """Promote a marked-useful interest into 1–3 claims on today's plan.

    Strategy (pinned): create a note stub for Asia/Shanghai *today*, then
    ``ingest_note(..., add_plan_item=True)`` so claims appear on the daily
    verify brief for examine. Idempotent via ``content.promoted_claim_ids``.
    """
    from gotit.db.ops.note import add_note, ingest_note

    row = await session.get(MemoryEntryRow, interest_id)
    if row is None or row.user_id != user_id or row.kind != KIND_INTEREST:
        raise KeyError(f"interest not found: {interest_id}")

    content = dict(row.content or {})
    existing_ids = [
        UUID(str(x))
        for x in (content.get("promoted_claim_ids") or [])
        if str(x).strip()
    ]
    if existing_ids:
        claim_rows = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.user_id == user_id,
                        ClaimRow.id.in_(existing_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        by_id = {c.id: c for c in claim_rows}
        restored = [_claim_view(by_id[cid]) for cid in existing_ids if cid in by_id]
        plan_ids = [
            UUID(str(x))
            for x in (content.get("promoted_plan_item_ids") or [])
            if str(x).strip()
        ]
        note_raw = content.get("promoted_note_id")
        return InterestPromoteResult(
            ok=True,
            interest_id=interest_id,
            already_promoted=True,
            note_id=UUID(str(note_raw)) if note_raw else None,
            claims=restored,
            plan_item_ids=plan_ids,
        )

    topic = (row.topic or "").strip() or None
    feed = content.get("feed_id")
    if not topic and feed:
        topic = f"feed:{feed}"

    if claims is None:
        texts = _candidate_texts_from_interest(content, claim_texts=claim_texts)
        accepted: list[Claim] = []
        last_reason: str | None = None
        for text in texts:
            reason = claim_reject_reason(text)
            if reason:
                last_reason = reason
                continue
            plain = _strip_html(text).strip()
            accepted.append(
                Claim(
                    text=plain[:500],
                    source_excerpt=plain[:200],
                    status=MasteryStatus.NOT_YET,
                    topic=topic,
                    tags=["digest", "interest"],
                )
            )
            if len(accepted) >= PROMOTE_MAX_CLAIMS:
                break
        if not accepted:
            return InterestPromoteResult(
                ok=False,
                interest_id=interest_id,
                reason=last_reason or "无可检验主张",
                rewrite_suggestion=_REWRITE_HINT,
            )
        claims = accepted
    else:
        filtered: list[Claim] = []
        last_reason = None
        for claim in claims[:PROMOTE_MAX_CLAIMS]:
            reason = claim_reject_reason(claim.text)
            if reason:
                last_reason = reason
                continue
            if topic and not claim.topic:
                claim.topic = topic
            if not claim.tags:
                claim.tags = ["digest", "interest"]
            filtered.append(claim)
        if not filtered:
            return InterestPromoteResult(
                ok=False,
                interest_id=interest_id,
                reason=last_reason or "无可检验主张",
                rewrite_suggestion=_REWRITE_HINT,
            )
        claims = filtered

    target_day = day
    if target_day is None:
        target_day = datetime.now(_PROMOTE_TZ).date()

    title = _strip_html(str(content.get("title") or "")).strip() or "资讯主张"
    body = interest_material(content) or title
    note = await add_note(
        session,
        target_day,
        body,
        title=title[:200],
        tags=["digest", "interest"],
        user_id=user_id,
    )
    ingested = await ingest_note(
        session,
        note.id,
        claims=claims,
        user_id=user_id,
        add_plan_item=True,
    )
    raw_claims = ingested.get("claims")
    claim_payloads: list[Any] = raw_claims if isinstance(raw_claims, list) else []
    persisted = [
        Claim.model_validate(c) if isinstance(c, dict) else c
        for c in claim_payloads
    ]
    raw_plans = ingested.get("plan_items")
    plan_payloads: list[Any] = raw_plans if isinstance(raw_plans, list) else []
    plan_ids = [
        UUID(str(p["id"] if isinstance(p, dict) else p.id))
        for p in plan_payloads
    ]
    claim_ids = [c.id for c in persisted]

    content["promoted_claim_ids"] = [str(cid) for cid in claim_ids]
    content["promoted_plan_item_ids"] = [str(pid) for pid in plan_ids]
    content["promoted_note_id"] = str(note.id)
    row.content = content
    await session.flush()

    return InterestPromoteResult(
        ok=True,
        interest_id=interest_id,
        note_id=note.id,
        claims=persisted,
        plan_item_ids=plan_ids,
    )


async def list_shell_activity(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    kinds: list[str] | None = None,
    limit: int = 50,
) -> list[MemoryEntry]:
    """List recent shell_event and/or interest rows (newest first)."""
    want = kinds or [KIND_SHELL_EVENT, KIND_INTEREST]
    pooled: list[MemoryEntry] = []
    per = max(limit, 20)
    for kind in want:
        pooled.extend(
            await list_memory(session, user_id=user_id, kind=kind, limit=per)
        )
    pooled.sort(key=lambda e: e.created_at, reverse=True)
    return pooled[:limit]


_SHELL_ACTIVITY_KINDS = frozenset({KIND_SHELL_EVENT, KIND_INTEREST})


async def delete_shell_activity(
    session: AsyncSession,
    memory_id: UUID,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Delete one shell_event or interest row. Raises KeyError if missing."""
    row = await session.get(MemoryEntryRow, memory_id)
    if row is None or row.user_id != user_id:
        raise KeyError(f"shell activity not found: {memory_id}")
    if row.kind not in _SHELL_ACTIVITY_KINDS:
        raise ValueError(f"not shell activity kind: {row.kind}")
    await session.delete(row)
    await session.flush()


async def delete_shell_activity_many(
    session: AsyncSession,
    memory_ids: list[UUID],
    *,
    user_id: str = DEFAULT_USER_ID,
) -> int:
    """Delete shell_event/interest rows by id. Returns deleted count."""
    if not memory_ids:
        return 0
    deleted = 0
    for mid in memory_ids:
        row = await session.get(MemoryEntryRow, mid)
        if row is None or row.user_id != user_id:
            continue
        if row.kind not in _SHELL_ACTIVITY_KINDS:
            continue
        await session.delete(row)
        deleted += 1
    if deleted:
        await session.flush()
    return deleted


async def get_digest_prefs(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DigestPrefs:
    """Return stored digest prefs or curated AI defaults."""
    rows = await list_memory(
        session, user_id=user_id, kind=KIND_DIGEST_PREFS, limit=1
    )
    if not rows:
        return default_digest_prefs()
    return _prefs_from_content(dict(rows[0].content or {}))


async def put_digest_prefs(
    session: AsyncSession,
    prefs: DigestPrefs,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> DigestPrefs:
    """Upsert singleton digest_prefs (long layer)."""
    cleaned = DigestPrefs.model_validate(prefs.model_dump(mode="json"))
    # morning/evening must never mix news into the plan job
    cleaned = cleaned.model_copy(
        update={"evening_include_news": False, "morning_include_news": False}
    )
    if cleaned.news_enabled and not (cleaned.news_cron or "").strip():
        cleaned = cleaned.model_copy(update={"news_cron": "0 20 * * *"})
    stmt = (
        select(MemoryEntryRow)
        .where(
            MemoryEntryRow.user_id == user_id,
            MemoryEntryRow.kind == KIND_DIGEST_PREFS,
        )
        .order_by(MemoryEntryRow.created_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    payload = cleaned.model_dump(mode="json")
    if row is None:
        entry = await add_memory(
            session,
            user_id=user_id,
            layer="long",
            kind=KIND_DIGEST_PREFS,
            topic="digest",
            content=payload,
            source={"skill": "digest"},
        )
        return _prefs_from_content(dict(entry.content or {}))
    row.content = payload
    row.topic = "digest"
    await session.flush()
    return _prefs_from_content(dict(row.content or {}))


def _digest_repo_root() -> Path:
    # src/gotit/db/ops/shell.py → repo root
    return Path(__file__).resolve().parents[4]


def sync_digest_openclaw_cron(*, timeout_s: float = 180.0) -> DigestCronSyncResult:
    """Run skills/digest/install-cron.sh (needs openclaw on PATH + Gateway).

    Local companion OS only: API host must be the Mac that runs OpenClaw.
    """
    import os
    import subprocess

    root = _digest_repo_root()
    script = root / "skills" / "digest" / "install-cron.sh"
    if not script.is_file():
        return DigestCronSyncResult(
            ok=False,
            exit_code=127,
            detail=f"install-cron.sh not found: {script}",
        )

    try:
        proc = subprocess.run(
            ["bash", str(script)],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=os.environ.copy(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        err = exc.stderr if isinstance(exc.stderr, str) else ""
        return DigestCronSyncResult(
            ok=False,
            exit_code=124,
            stdout=(out or "")[-4000:],
            stderr=(err or "")[-2000:],
            detail=f"install-cron.sh timed out after {timeout_s:.0f}s",
        )
    except OSError as exc:
        return DigestCronSyncResult(
            ok=False,
            exit_code=127,
            detail=f"无法启动 install-cron.sh：{exc}",
        )

    stdout = (proc.stdout or "")[-4000:]
    stderr = (proc.stderr or "")[-2000:]
    ok = proc.returncode == 0
    detail = None
    if not ok:
        detail = (
            (stderr.strip().splitlines() or [""])[-1]
            or (stdout.strip().splitlines() or [""])[-1]
            or f"exit {proc.returncode}"
        )
    return DigestCronSyncResult(
        ok=ok,
        exit_code=proc.returncode,
        stdout=stdout,
        stderr=stderr,
        detail=detail,
    )


async def build_profile_v0(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    limit_per_kind: int = 200,
) -> ProfileView:
    """Aggregate trajectory failures/passes + interest counts by topic."""
    trajectories = await list_memory(
        session, user_id=user_id, kind=KIND_TRAJECTORY, limit=limit_per_kind
    )
    interests = await list_memory(
        session, user_id=user_id, kind=KIND_INTEREST, limit=limit_per_kind
    )
    shells = await list_memory(
        session, user_id=user_id, kind=KIND_SHELL_EVENT, limit=limit_per_kind
    )

    stats: dict[str, ProfileTopicStat] = {}

    def _topic_key(raw: str | None) -> str:
        t = (raw or "").strip()
        return t if t else "(untagged)"

    def _stat(topic: str) -> ProfileTopicStat:
        if topic not in stats:
            stats[topic] = ProfileTopicStat(topic=topic)
        return stats[topic]

    for e in trajectories:
        st = _stat(_topic_key(e.topic))
        verdict = str((e.content or {}).get("verdict") or "").lower()
        if verdict in {"passed", "pass", "true"}:
            st.trajectory_passes += 1
        elif verdict:
            st.trajectory_failures += 1

    for e in interests:
        topic = e.topic
        if not topic:
            feed = (e.content or {}).get("feed_id")
            topic = f"feed:{feed}" if feed else "interest"
        _stat(_topic_key(str(topic))).interest_count += 1

    topics = sorted(
        stats.values(),
        key=lambda s: (s.trajectory_failures, s.interest_count),
        reverse=True,
    )
    weak = [t.topic for t in topics if t.trajectory_failures > 0][:8]
    return ProfileView(
        topics=topics,
        weak_topics=weak,
        interest_total=len(interests),
        shell_event_total=len(shells),
        trajectory_total=len(trajectories),
    )


async def build_graph_v0(
    session: AsyncSession,
    *,
    user_id: str = DEFAULT_USER_ID,
    claim_limit: int = 200,
    interest_limit: int = 100,
    active_days: int = 14,
) -> GraphView:
    """claim–topic–project + confused_with / depends_on; interest may attach to topic."""
    from datetime import UTC, datetime, timedelta

    from gotit.core.mastery_graph import CONFUSED_THRESHOLD
    from gotit.db.ops.graph import (
        fail_counts_by_claim,
        latest_fail_by_claim,
        list_confused_edges,
        list_depends_edges,
        mastered_claim_ids,
    )

    stmt = (
        select(ClaimRow)
        .where(ClaimRow.user_id == user_id)
        .order_by(ClaimRow.id)
        .limit(claim_limit)
    )
    claims = list((await session.execute(stmt)).scalars().all())
    projects = list(
        (
            await session.execute(
                select(ProjectRow).where(ProjectRow.user_id == user_id)
            )
        )
        .scalars()
        .all()
    )
    interests = await list_memory(
        session, user_id=user_id, kind=KIND_INTEREST, limit=interest_limit
    )
    claim_uuids = [c.id for c in claims]
    fail_counts = await fail_counts_by_claim(
        session, user_id=user_id, claim_ids=claim_uuids
    )
    latest_fails = await latest_fail_by_claim(
        session, user_id=user_id, claim_ids=claim_uuids
    )
    confused = await list_confused_edges(session, user_id=user_id, min_weight=1)
    depends = await list_depends_edges(session, user_id=user_id)
    prereq_ids = list({e.target_claim_id for e in depends})
    mastered = await mastered_claim_ids(
        session, user_id=user_id, claim_ids=prereq_ids
    )

    now = datetime.now(UTC)
    window = timedelta(days=max(1, active_days))

    def _is_recent(fail: object) -> bool:
        created = getattr(fail, "created_at", None)
        if created is None:
            return False
        if getattr(created, "tzinfo", None) is None:
            created = created.replace(tzinfo=UTC)
        delta = now - created
        return bool(delta <= window)

    topic_by_id = {c.id: (c.topic or "").strip() or None for c in claims}
    label_by_id = {
        c.id: (_strip_html(c.text)[:120] or "未命名命题") for c in claims
    }

    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    def _add_node(node: GraphNode) -> None:
        nodes[node.id] = node

    for p in projects:
        _add_node(
            GraphNode(
                id=f"project:{p.id}",
                type="project",
                label=p.name,
                meta={"status": p.status},
            )
        )

    for row in claims:
        claim = _claim_view(row)
        cid = f"claim:{claim.id}"
        status = claim.status.value if hasattr(claim.status, "value") else str(claim.status)
        plain = _strip_html(claim.text)[:120] or "未命名命题"
        latest = latest_fails.get(claim.id)
        pref = claim.preferred_check_mode
        pref_val = pref.value if pref is not None and hasattr(pref, "value") else pref
        meta: dict[str, object] = {
            "claim_id": str(claim.id),
            "status": status,
            "fail_count": fail_counts.get(claim.id, 0),
            "topic": claim.topic,
            "preferred_check_mode": pref_val,
            "project_id": str(claim.project_id) if claim.project_id else None,
            "last_fail_at": latest.created_at.isoformat() if latest else None,
            "last_fail_reason": (
                ((latest.reason or latest.gate_verdict) or "").strip()[:80] or None
                if latest
                else None
            ),
            "recent": bool(latest and _is_recent(latest)),
        }
        _add_node(
            GraphNode(
                id=cid,
                type="claim",
                label=plain,
                meta=meta,
            )
        )
        if claim.topic:
            tid = f"topic:{claim.topic}"
            _add_node(GraphNode(id=tid, type="topic", label=claim.topic))
            edges.append(GraphEdge(source=cid, target=tid, rel="has_topic"))
        if claim.project_id:
            pid = f"project:{claim.project_id}"
            if pid not in nodes:
                _add_node(
                    GraphNode(id=pid, type="project", label=str(claim.project_id)[:8])
                )
            edges.append(GraphEdge(source=cid, target=pid, rel="in_project"))

    for e in interests:
        topic = (e.topic or "").strip()
        if not topic:
            continue
        tid = f"topic:{topic}"
        _add_node(GraphNode(id=tid, type="topic", label=topic))
        iid = f"interest:{e.id}"
        title = str((e.content or {}).get("title") or "interest")[:80]
        _add_node(GraphNode(id=iid, type="interest", label=title))
        edges.append(GraphEdge(source=iid, target=tid, rel="interest_topic"))

    claim_ids = {c.id for c in claims}
    for edge in confused:
        if edge.source_claim_id not in claim_ids or edge.target_claim_id not in claim_ids:
            continue
        w = int(edge.weight)
        src_t = topic_by_id.get(edge.source_claim_id)
        tgt_t = topic_by_id.get(edge.target_claim_id)
        cross = bool(src_t and tgt_t and src_t != tgt_t)
        tip_src = latest_fails.get(edge.source_claim_id)
        tip_tgt = latest_fails.get(edge.target_claim_id)
        tip = tip_src or tip_tgt
        if tip_src and tip_tgt:
            tip = (
                tip_src
                if tip_src.created_at >= tip_tgt.created_at
                else tip_tgt
            )
        reason = None
        if tip is not None:
            reason = ((tip.reason or tip.gate_verdict) or "").strip()[:80] or None
        edges.append(
            GraphEdge(
                source=f"claim:{edge.source_claim_id}",
                target=f"claim:{edge.target_claim_id}",
                rel="confused_with",
                weight=w,
                meta={
                    "active": w >= CONFUSED_THRESHOLD,
                    "cross_topic": cross,
                    "source_topic": src_t,
                    "target_topic": tgt_t,
                    "reason_summary": reason,
                },
            )
        )

    for edge in depends:
        if edge.source_claim_id not in claim_ids or edge.target_claim_id not in claim_ids:
            continue
        unmet = edge.target_claim_id not in mastered
        edges.append(
            GraphEdge(
                source=f"claim:{edge.source_claim_id}",
                target=f"claim:{edge.target_claim_id}",
                rel="depends_on",
                weight=int(edge.weight),
                meta={
                    "unmet": unmet,
                    "prereq_label": label_by_id.get(edge.target_claim_id, "")[:80]
                    or None,
                },
            )
        )

    return GraphView(nodes=list(nodes.values()), edges=edges)
