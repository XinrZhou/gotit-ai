#!/usr/bin/env python3
"""Seed mock mastery-graph data for Settings → 图谱 preview.

Usage:
  uv run python scripts/seed_mastery_graph.py
  uv run python scripts/seed_mastery_graph.py --reset   # delete prior mock-* claims first
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import delete, select

from gotit.api.settings import get_settings
from gotit.core.mastery_graph import canonical_claim_pair
from gotit.core.models import MasteryStatus
from gotit.db.models import ClaimRow, FailEventRow, GraphEdgeRow, ProjectRow
from gotit.db.runtime import ensure_db
from gotit.db.session import session_scope

MOCK_TAG = "mock-mastery-graph"

# topic → claims (short labels look good on the force graph)
TOPICS: dict[str, list[str]] = {
    "指针与内存": [
        "指针保存的是地址，不是对象本身",
        "数组名在多数表达式里会退化成指针",
        "free 之后必须把指针置空，否则悬空",
        "栈对象离开作用域自动释放，堆需要显式 free",
    ],
    "Transformer": [
        "Self-Attention 用 Q/K 算权重再加权 V",
        "Softmax 把 logits 归一成概率分布",
        "多头注意力是多组 QKV 再拼回",
        "位置编码弥补 Attention 无序的问题",
    ],
    "面试项目": [
        "gotit 的 gate 必须是确定性代码，不能交给 LLM",
        "验证闭环：examine → critic → gate → trajectory",
        "掌握图谱边从失败事件长出来，不是模型瞎编",
    ],
}

# undirected confuse pairs as (topic, i, j, weight)
CONFUSED: list[tuple[str, int, int, int]] = [
    ("指针与内存", 0, 1, 3),  # active
    ("指针与内存", 1, 2, 2),  # active
    ("指针与内存", 2, 3, 1),  # inactive preview
    ("Transformer", 0, 1, 4),
    ("Transformer", 1, 2, 2),
    ("Transformer", 0, 2, 1),
    ("面试项目", 0, 1, 3),
    ("面试项目", 1, 2, 2),
]


async def _reset_mock(user_id: str) -> int:
    async with session_scope() as session:
        claims = list(
            (
                await session.execute(
                    select(ClaimRow).where(
                        ClaimRow.user_id == user_id,
                        ClaimRow.source_excerpt == MOCK_TAG,
                    )
                )
            )
            .scalars()
            .all()
        )
        ids = [c.id for c in claims]
        if not ids:
            return 0
        await session.execute(
            delete(GraphEdgeRow).where(
                GraphEdgeRow.user_id == user_id,
                GraphEdgeRow.source_claim_id.in_(ids),
            )
        )
        await session.execute(
            delete(GraphEdgeRow).where(
                GraphEdgeRow.user_id == user_id,
                GraphEdgeRow.target_claim_id.in_(ids),
            )
        )
        await session.execute(delete(FailEventRow).where(FailEventRow.claim_id.in_(ids)))
        await session.execute(delete(ClaimRow).where(ClaimRow.id.in_(ids)))
        proj = (
            await session.execute(
                select(ProjectRow).where(
                    ProjectRow.user_id == user_id,
                    ProjectRow.name == "Mock · 掌握图谱预览",
                )
            )
        ).scalar_one_or_none()
        if proj is not None:
            await session.delete(proj)
        return len(ids)


async def seed(*, reset: bool) -> None:
    settings = get_settings()
    user_id = settings.gotit_user_id
    await ensure_db()

    if reset:
        n = await _reset_mock(user_id)
        print(f"reset: removed {n} mock claims")

    async with session_scope() as session:
        project = ProjectRow(
            id=uuid4(),
            user_id=user_id,
            name="Mock · 掌握图谱预览",
            goal="seed_mastery_graph.py",
            status="active",
            created_at=datetime.now(UTC),
        )
        session.add(project)
        await session.flush()

        by_topic: dict[str, list[ClaimRow]] = {}
        for topic, texts in TOPICS.items():
            rows: list[ClaimRow] = []
            for i, text in enumerate(texts):
                row = ClaimRow(
                    id=uuid4(),
                    user_id=user_id,
                    text=text,
                    source_excerpt=MOCK_TAG,
                    status=(
                        MasteryStatus.IN_PROGRESS.value
                        if i % 2 == 0
                        else MasteryStatus.NOT_YET.value
                    ),
                    topic=topic,
                    tags=[MOCK_TAG, topic],
                    project_id=project.id if topic == "面试项目" else None,
                )
                session.add(row)
                rows.append(row)
            by_topic[topic] = rows
        await session.flush()

        # fail events (drive fail_count on nodes)
        fail_specs: list[tuple[ClaimRow, str, str]] = []
        for topic, rows in by_topic.items():
            for i, row in enumerate(rows):
                times = 3 - min(i, 2)  # first claims fail more
                for t in range(times):
                    fail_specs.append(
                        (
                            row,
                            "owe_next" if t % 2 == 0 else "almost",
                            f"mock fail #{t + 1} on {topic}",
                        )
                    )
        for row, verdict, reason in fail_specs:
            session.add(
                FailEventRow(
                    id=uuid4(),
                    user_id=user_id,
                    claim_id=row.id,
                    topic=row.topic,
                    gate_verdict=verdict,
                    score=0.4,
                    reason=reason,
                    created_at=datetime.now(UTC),
                )
            )

        for topic, i, j, weight in CONFUSED:
            a = by_topic[topic][i]
            b = by_topic[topic][j]
            src, tgt = canonical_claim_pair(a.id, b.id)
            session.add(
                GraphEdgeRow(
                    id=uuid4(),
                    user_id=user_id,
                    source_claim_id=src,
                    target_claim_id=tgt,
                    rel="confused_with",
                    weight=weight,
                    updated_at=datetime.now(UTC),
                )
            )

        n_claims = sum(len(v) for v in by_topic.values())
        n_edges = len(CONFUSED)
        print(
            f"seeded user={user_id}: {n_claims} claims, "
            f"{len(fail_specs)} fail_events, {n_edges} confused edges, 1 project"
        )
        print("Open Settings → 图谱 and hit 刷新")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset",
        action="store_true",
        help="remove previous mock-mastery-graph claims before seeding",
    )
    args = parser.parse_args()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()
