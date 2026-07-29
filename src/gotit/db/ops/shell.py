"""OpenClaw shell writeback + obs (profile / graph v0) over memory + claims."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gotit.core.models import (
    GraphEdge,
    GraphNode,
    GraphView,
    MemoryEntry,
    ProfileTopicStat,
    ProfileView,
)
from gotit.db.models import ClaimRow, ProjectRow
from gotit.db.ops._common import DEFAULT_USER_ID, _claim_view
from gotit.db.ops.memory import add_memory, list_memory

KIND_SHELL_EVENT = "shell_event"
KIND_INTEREST = "interest"
KIND_TRAJECTORY = "trajectory"


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
) -> MemoryEntry:
    """Persist a digest/cron push as working-layer shell_event."""
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
    content: dict[str, Any] = {
        "job": job,
        "items": normalized,
        "due_summary": list(due_summary or []),
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
) -> GraphView:
    """claim–topic–project edges; interest may attach to topic only (no RSS nodes)."""
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
        _add_node(
            GraphNode(
                id=cid,
                type="claim",
                label=claim.text[:120],
                meta={"status": status},
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

    return GraphView(nodes=list(nodes.values()), edges=edges)
