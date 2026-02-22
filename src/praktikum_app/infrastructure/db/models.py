"""SQLAlchemy models for application persistence."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from praktikum_app.infrastructure.db.base import Base


class CourseModel(Base):
    """Imported course aggregate root."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sources: Mapped[list[CourseSourceModel]] = relationship(back_populates="course")
    raw_texts: Mapped[list[RawTextModel]] = relationship(back_populates="course")
    modules: Mapped[list[ModuleModel]] = relationship(back_populates="course")
    deadlines: Mapped[list[DeadlineModel]] = relationship(back_populates="course")
    llm_calls: Mapped[list[LlmCallModel]] = relationship(back_populates="course")


class CourseSourceModel(Base):
    """Metadata about original source used to import course text."""

    __tablename__ = "course_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_strategy: Mapped[str | None] = mapped_column(String(64), nullable=True)
    likely_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    course: Mapped[CourseModel] = relationship(back_populates="sources")
    raw_texts: Mapped[list[RawTextModel]] = relationship(back_populates="source")


class RawTextModel(Base):
    """Normalized raw imported text."""

    __tablename__ = "raw_texts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("course_sources.id"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    length: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    course: Mapped[CourseModel] = relationship(back_populates="raw_texts")
    source: Mapped[CourseSourceModel] = relationship(back_populates="raw_texts")


class ModuleModel(Base):
    """Future module representation for parsed course plans."""

    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    course: Mapped[CourseModel] = relationship(back_populates="modules")
    deadlines: Mapped[list[DeadlineModel]] = relationship(back_populates="module")
    llm_calls: Mapped[list[LlmCallModel]] = relationship(back_populates="module")


class DeadlineModel(Base):
    """Future deadline representation for modules/courses."""

    __tablename__ = "deadlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    module_id: Mapped[str | None] = mapped_column(
        ForeignKey("modules.id"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="scheduled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    course: Mapped[CourseModel] = relationship(back_populates="deadlines")
    module: Mapped[ModuleModel | None] = relationship(back_populates="deadlines")


class LlmCallModel(Base):
    """LLM calls audit structure reserved for future integration."""

    __tablename__ = "llm_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    llm_call_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    course_id: Mapped[str | None] = mapped_column(
        ForeignKey("courses.id"),
        nullable=True,
        index=True,
    )
    module_id: Mapped[str | None] = mapped_column(
        ForeignKey("modules.id"),
        nullable=True,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    course: Mapped[CourseModel | None] = relationship(back_populates="llm_calls")
    module: Mapped[ModuleModel | None] = relationship(back_populates="llm_calls")
