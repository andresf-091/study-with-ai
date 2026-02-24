"""Add practice_tasks table and llm_calls task_type audit field."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_practice_tasks_and_llm_task_type"
down_revision = "0003_llm_call_output_audit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes required for practice generation history."""
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.add_column(sa.Column("task_type", sa.String(length=32), nullable=True))

    op.create_index("ix_llm_calls_task_type", "llm_calls", ["task_type"])

    op.create_table(
        "practice_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=36), nullable=False),
        sa.Column("llm_call_id", sa.String(length=64), nullable=False),
        sa.Column("generation_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_index", sa.Integer(), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("expected_outline", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_practice_tasks_course_id", "practice_tasks", ["course_id"])
    op.create_index("ix_practice_tasks_module_id", "practice_tasks", ["module_id"])
    op.create_index("ix_practice_tasks_generation_id", "practice_tasks", ["generation_id"])


def downgrade() -> None:
    """Revert practice generation schema additions."""
    op.drop_index("ix_practice_tasks_generation_id", table_name="practice_tasks")
    op.drop_index("ix_practice_tasks_module_id", table_name="practice_tasks")
    op.drop_index("ix_practice_tasks_course_id", table_name="practice_tasks")
    op.drop_table("practice_tasks")

    op.drop_index("ix_llm_calls_task_type", table_name="llm_calls")
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.drop_column("task_type")
