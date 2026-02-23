"""Add course plan fields for modules/deadlines review and persistence."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_course_plan_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes required for CoursePlan v1 persistence."""
    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("start_date", sa.Date(), nullable=True))

    with op.batch_alter_table("modules") as batch_op:
        batch_op.add_column(
            sa.Column(
                "goals_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(
            sa.Column(
                "topics_json",
                sa.Text(),
                nullable=False,
                server_default="[]",
            )
        )
        batch_op.add_column(sa.Column("estimated_hours", sa.Integer(), nullable=True))

    with op.batch_alter_table("deadlines") as batch_op:
        batch_op.add_column(
            sa.Column(
                "position",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.String(length=32),
                nullable=False,
                server_default="deadline",
            )
        )
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    """Revert CoursePlan v1 schema changes."""
    with op.batch_alter_table("deadlines") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("kind")
        batch_op.drop_column("position")

    with op.batch_alter_table("modules") as batch_op:
        batch_op.drop_column("estimated_hours")
        batch_op.drop_column("topics_json")
        batch_op.drop_column("goals_json")

    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_column("start_date")
        batch_op.drop_column("description")
