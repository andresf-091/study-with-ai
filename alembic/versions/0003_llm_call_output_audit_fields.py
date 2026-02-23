"""Add llm_calls output payload and validation diagnostics fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_llm_call_output_audit_fields"
down_revision = "0002_course_plan_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema changes for richer LLM audit diagnostics."""
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.add_column(sa.Column("output_hash", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("output_length", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("output_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("validation_errors", sa.Text(), nullable=True))


def downgrade() -> None:
    """Revert LLM audit diagnostics columns."""
    with op.batch_alter_table("llm_calls") as batch_op:
        batch_op.drop_column("validation_errors")
        batch_op.drop_column("output_text")
        batch_op.drop_column("output_length")
        batch_op.drop_column("output_hash")
