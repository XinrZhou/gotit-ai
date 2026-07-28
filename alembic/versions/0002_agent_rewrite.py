"""Agent rewrite: claim topic/tags, memory, prompts, harness."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_agent_rewrite"
down_revision: str | None = "0001_daily_plan_notes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_type() -> sa.types.TypeEngine:
    """JSONB on Postgres, JSON elsewhere (matches ORM JSONB TypeDecorator)."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    # claims: add topic + tags
    with op.batch_alter_table("claims") as batch:
        batch.add_column(sa.Column("topic", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("tags", _json_type(), nullable=False, server_default="[]"))
        batch.create_index("ix_claims_topic", ["topic"])

    # memory_entries
    op.create_table(
        "memory_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("layer", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("topic", sa.String(length=200), nullable=True),
        sa.Column("content", _json_type(), nullable=False, server_default="{}"),
        sa.Column("source", _json_type(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_memory_entries_user_id", "memory_entries", ["user_id"])
    op.create_index("ix_memory_entries_layer", "memory_entries", ["layer"])
    op.create_index("ix_memory_entries_topic", "memory_entries", ["topic"])

    # prompt_versions
    op.create_table(
        "prompt_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_name", sa.String(length=32), nullable=False),
        sa.Column("version_label", sa.String(length=64), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("config", _json_type(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_name", "version_label", name="uq_prompt_agent_version"),
    )
    op.create_index("ix_prompt_versions_agent_name", "prompt_versions", ["agent_name"])

    # harness_runs
    op.create_table(
        "harness_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("git_sha", sa.String(length=40), nullable=True),
        sa.Column("prompt_versions", _json_type(), nullable=False, server_default="{}"),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("case_set", sa.String(length=64), nullable=False),
        sa.Column("summary", _json_type(), nullable=False, server_default="{}"),
        sa.Column("verdict", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_harness_runs_label", "harness_runs", ["label"])

    # harness_case_results
    op.create_table(
        "harness_case_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=64), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("metrics", _json_type(), nullable=False, server_default="{}"),
        sa.Column("trace", _json_type(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["harness_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_harness_case_results_run_id", "harness_case_results", ["run_id"])
    op.create_index("ix_harness_case_results_case_id", "harness_case_results", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_harness_case_results_case_id", table_name="harness_case_results")
    op.drop_index("ix_harness_case_results_run_id", table_name="harness_case_results")
    op.drop_table("harness_case_results")
    op.drop_index("ix_harness_runs_label", table_name="harness_runs")
    op.drop_table("harness_runs")
    op.drop_index("ix_prompt_versions_agent_name", table_name="prompt_versions")
    op.drop_table("prompt_versions")
    op.drop_index("ix_memory_entries_topic", table_name="memory_entries")
    op.drop_index("ix_memory_entries_layer", table_name="memory_entries")
    op.drop_index("ix_memory_entries_user_id", table_name="memory_entries")
    op.drop_table("memory_entries")
    op.drop_index("ix_claims_topic", table_name="claims")
    with op.batch_alter_table("claims") as batch:
        batch.drop_column("tags")
        batch.drop_column("topic")
