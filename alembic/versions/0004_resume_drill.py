"""Resume-driven drill: resumes / drill_materials / drill_sessions tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_resume_drill"
down_revision: str | None = "0003_project_drill"
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
        "resumes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("upload_id", sa.Uuid(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("document", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_resumes_user"),
    )

    op.create_table(
        "drill_materials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_drill_materials_user_id", "drill_materials", ["user_id"])

    op.create_table(
        "drill_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("resume_id", sa.Uuid(), nullable=False),
        sa.Column("round", sa.String(length=16), nullable=False),
        sa.Column("direction", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("messages", _json_type(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
    )
    op.create_index("ix_drill_sessions_user_id", "drill_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_drill_sessions_user_id", table_name="drill_sessions")
    op.drop_table("drill_sessions")
    op.drop_index("ix_drill_materials_user_id", table_name="drill_materials")
    op.drop_table("drill_materials")
    op.drop_table("resumes")
