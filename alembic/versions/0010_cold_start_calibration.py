"""Cold-start calibration: claim.calibration JSON + calibration_sessions."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010_cold_start_calibration"
down_revision: str | None = "0009_interviews"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("calibration", _json_type(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "calibration_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("theta", sa.Float(), nullable=False, server_default="3.0"),
        sa.Column("se", sa.Float(), nullable=False, server_default="1.5"),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stop_reason", sa.String(length=32), nullable=True),
        sa.Column("scope", _json_type(), nullable=False, server_default="{}"),
        sa.Column("pool_claim_ids", _json_type(), nullable=False, server_default="[]"),
        sa.Column("answered_claim_ids", _json_type(), nullable=False, server_default="[]"),
        sa.Column("downweight_claim_ids", _json_type(), nullable=False, server_default="[]"),
        sa.Column("last_knowledge_key", sa.String(length=200), nullable=True),
        sa.Column("current_claim_id", sa.Uuid(), nullable=True),
        sa.Column("recent_delta_theta", _json_type(), nullable=False, server_default="[]"),
        sa.Column("trace", _json_type(), nullable=False, server_default="[]"),
        sa.Column("summary", _json_type(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_calibration_sessions_user_id",
        "calibration_sessions",
        ["user_id"],
    )
    op.create_index(
        "ix_calibration_sessions_status",
        "calibration_sessions",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_calibration_sessions_status", table_name="calibration_sessions")
    op.drop_index("ix_calibration_sessions_user_id", table_name="calibration_sessions")
    op.drop_table("calibration_sessions")
    op.drop_column("claims", "calibration")
