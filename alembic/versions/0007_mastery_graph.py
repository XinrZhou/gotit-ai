"""Mastery graph: fail_events + graph_edges."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007_mastery_graph"
down_revision: str | None = "0006_profile_center"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fail_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=True),
        sa.Column("gate_verdict", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fail_events_user_id", "fail_events", ["user_id"])
    op.create_index("ix_fail_events_claim_id", "fail_events", ["claim_id"])
    op.create_index("ix_fail_events_topic", "fail_events", ["topic"])
    op.create_index("ix_fail_events_created_at", "fail_events", ["created_at"])

    op.create_table(
        "graph_edges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("source_claim_id", sa.Uuid(), nullable=False),
        sa.Column("target_claim_id", sa.Uuid(), nullable=False),
        sa.Column("rel", sa.String(length=32), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["source_claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["target_claim_id"], ["claims.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "source_claim_id",
            "target_claim_id",
            "rel",
            name="uq_graph_edges_user_pair_rel",
        ),
    )
    op.create_index("ix_graph_edges_user_id", "graph_edges", ["user_id"])
    op.create_index("ix_graph_edges_source_claim_id", "graph_edges", ["source_claim_id"])
    op.create_index("ix_graph_edges_target_claim_id", "graph_edges", ["target_claim_id"])


def downgrade() -> None:
    op.drop_table("graph_edges")
    op.drop_table("fail_events")
