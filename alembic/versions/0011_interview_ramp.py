"""Interview countdown ramp: last_ramp_nudge_at on interview_events."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011_interview_ramp"
down_revision: str | None = "0010_cold_start_calibration"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "interview_events",
        sa.Column("last_ramp_nudge_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("interview_events", "last_ramp_nudge_at")
