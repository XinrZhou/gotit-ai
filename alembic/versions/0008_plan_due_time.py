"""Add plan_items.due_time (HH:MM)."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0008_plan_due_time"
down_revision: str | None = "0007_mastery_graph"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "plan_items",
        sa.Column("due_time", sa.String(length=5), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plan_items", "due_time")
