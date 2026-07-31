"""depends_on edges reuse graph_edges; index by (user_id, rel)."""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_depends_on"
down_revision: str | None = "0012_day_close"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Directed depends_on lives in graph_edges.rel (no new table).
    # Index speeds list_depends_edges / confuse filters by user+rel.
    op.create_index(
        "ix_graph_edges_user_id_rel",
        "graph_edges",
        ["user_id", "rel"],
    )


def downgrade() -> None:
    op.drop_index("ix_graph_edges_user_id_rel", table_name="graph_edges")
