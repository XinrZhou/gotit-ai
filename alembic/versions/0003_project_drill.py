"""Project drill: projects table + project_id on notes/claims/plan_items."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_project_drill"
down_revision: str | None = "0002_agent_rewrite"
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
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column("tech_stack", _json_type(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_user_id", "projects", ["user_id"])
    op.create_index("ix_projects_status", "projects", ["status"])

    with op.batch_alter_table("day_notes") as batch:
        batch.add_column(
            sa.Column("project_id", sa.Uuid(), nullable=True)
        )
        batch.create_index("ix_day_notes_project_id", ["project_id"])

    with op.batch_alter_table("claims") as batch:
        batch.add_column(sa.Column("project_id", sa.Uuid(), nullable=True))
        batch.create_index("ix_claims_project_id", ["project_id"])

    with op.batch_alter_table("plan_items") as batch:
        batch.add_column(sa.Column("project_id", sa.Uuid(), nullable=True))
        batch.create_index("ix_plan_items_project_id", ["project_id"])


def downgrade() -> None:
    with op.batch_alter_table("plan_items") as batch:
        batch.drop_index("ix_plan_items_project_id")
        batch.drop_column("project_id")

    with op.batch_alter_table("claims") as batch:
        batch.drop_index("ix_claims_project_id")
        batch.drop_column("project_id")

    with op.batch_alter_table("day_notes") as batch:
        batch.drop_index("ix_day_notes_project_id")
        batch.drop_column("project_id")

    op.drop_index("ix_projects_status", table_name="projects")
    op.drop_index("ix_projects_user_id", table_name="projects")
    op.drop_table("projects")
