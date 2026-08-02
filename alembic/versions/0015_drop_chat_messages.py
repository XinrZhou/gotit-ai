"""Drop unused plan-item chat_messages table."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0015_drop_chat_messages"
down_revision: str | None = "0014_claim_preferred_mode"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Table was often created via SQLAlchemy create_all, not earlier revisions.
    bind = op.get_bind()
    if "chat_messages" in sa.inspect(bind).get_table_names():
        op.drop_table("chat_messages")


def downgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_item_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["plan_item_id"], ["plan_items.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_plan_item_id", "chat_messages", ["plan_item_id"])
