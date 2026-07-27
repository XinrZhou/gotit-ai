"""Initial schema: learning_days, plan_items, day_notes, claims."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_daily_plan_notes"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source_note_id", sa.Uuid(), nullable=True),
        sa.Column("next_review_at", sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_claims_user_id", "claims", ["user_id"])

    op.create_table(
        "learning_days",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "day", name="uq_learning_days_user_day"),
    )
    op.create_index("ix_learning_days_user_id", "learning_days", ["user_id"])
    op.create_index("ix_learning_days_day", "learning_days", ["day"])

    op.create_table(
        "day_notes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["day_id"], ["learning_days.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_day_notes_day_id", "day_notes", ["day_id"])

    op.create_table(
        "plan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("day_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("claim_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(["claim_id"], ["claims.id"]),
        sa.ForeignKeyConstraint(["day_id"], ["learning_days.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_items_day_id", "plan_items", ["day_id"])


def downgrade() -> None:
    op.drop_index("ix_plan_items_day_id", table_name="plan_items")
    op.drop_table("plan_items")
    op.drop_index("ix_day_notes_day_id", table_name="day_notes")
    op.drop_table("day_notes")
    op.drop_index("ix_learning_days_day", table_name="learning_days")
    op.drop_index("ix_learning_days_user_id", table_name="learning_days")
    op.drop_table("learning_days")
    op.drop_index("ix_claims_user_id", table_name="claims")
    op.drop_table("claims")
