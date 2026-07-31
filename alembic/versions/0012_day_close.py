"""Day close ritual: closed_at + short wrap summary on learning_days."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_day_close"
down_revision: str | None = "0011_interview_ramp"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "learning_days",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "learning_days",
        sa.Column("close_passed_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "learning_days",
        sa.Column("close_still_owed_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "learning_days",
        sa.Column("close_note", sa.String(length=200), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("learning_days", "close_note")
    op.drop_column("learning_days", "close_still_owed_count")
    op.drop_column("learning_days", "close_passed_count")
    op.drop_column("learning_days", "closed_at")
