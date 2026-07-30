"""Interview events for companion-os P3d."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009_interviews"
down_revision: str | None = "0008_plan_due_time"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "interview_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("company", sa.String(length=200), nullable=False),
        sa.Column("role_title", sa.String(length=200), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("round", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "remind_offsets_hours",
            _json_type(),
            nullable=False,
            server_default="[-24, -2]",
        ),
        sa.Column("last_reminded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_interview_events_user_id", "interview_events", ["user_id"])
    op.create_index("ix_interview_events_scheduled_at", "interview_events", ["scheduled_at"])
    op.create_index("ix_interview_events_status", "interview_events", ["status"])


def downgrade() -> None:
    op.drop_index("ix_interview_events_status", table_name="interview_events")
    op.drop_index("ix_interview_events_scheduled_at", table_name="interview_events")
    op.drop_index("ix_interview_events_user_id", table_name="interview_events")
    op.drop_table("interview_events")
