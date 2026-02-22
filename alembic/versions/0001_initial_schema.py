"""Create initial SQLite schema for study-with-ai."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply initial schema."""
    op.create_table(
        "courses",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "course_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("extraction_strategy", sa.String(length=64), nullable=True),
        sa.Column("likely_scanned", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_course_sources_course_id", "course_sources", ["course_id"])

    op.create_table(
        "modules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_modules_course_id", "modules", ["course_id"])

    op.create_table(
        "raw_texts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("length", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["course_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_texts_content_hash", "raw_texts", ["content_hash"])
    op.create_index("ix_raw_texts_course_id", "raw_texts", ["course_id"])
    op.create_index("ix_raw_texts_source_id", "raw_texts", ["source_id"])

    op.create_table(
        "deadlines",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=False),
        sa.Column("module_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deadlines_course_id", "deadlines", ["course_id"])
    op.create_index("ix_deadlines_module_id", "deadlines", ["module_id"])

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("llm_call_id", sa.String(length=64), nullable=False),
        sa.Column("course_id", sa.String(length=36), nullable=True),
        sa.Column("module_id", sa.String(length=36), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"]),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("llm_call_id"),
    )
    op.create_index("ix_llm_calls_course_id", "llm_calls", ["course_id"])
    op.create_index("ix_llm_calls_llm_call_id", "llm_calls", ["llm_call_id"])
    op.create_index("ix_llm_calls_module_id", "llm_calls", ["module_id"])


def downgrade() -> None:
    """Revert initial schema."""
    op.drop_index("ix_llm_calls_module_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_llm_call_id", table_name="llm_calls")
    op.drop_index("ix_llm_calls_course_id", table_name="llm_calls")
    op.drop_table("llm_calls")

    op.drop_index("ix_deadlines_module_id", table_name="deadlines")
    op.drop_index("ix_deadlines_course_id", table_name="deadlines")
    op.drop_table("deadlines")

    op.drop_index("ix_raw_texts_source_id", table_name="raw_texts")
    op.drop_index("ix_raw_texts_course_id", table_name="raw_texts")
    op.drop_index("ix_raw_texts_content_hash", table_name="raw_texts")
    op.drop_table("raw_texts")

    op.drop_index("ix_modules_course_id", table_name="modules")
    op.drop_table("modules")

    op.drop_index("ix_course_sources_course_id", table_name="course_sources")
    op.drop_table("course_sources")

    op.drop_table("courses")
