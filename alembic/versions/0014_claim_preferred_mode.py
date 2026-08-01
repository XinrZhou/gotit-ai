"""claims.preferred_check_mode for form-follows-claim routing."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_claim_preferred_mode"
down_revision: str | None = "0013_depends_on"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("preferred_check_mode", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("claims", "preferred_check_mode")
