"""Engine/session bootstrap for SQLite persistence."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.infrastructure.db.config import get_database_path, make_sqlite_url


def create_sqlite_engine(database_path: Path) -> Engine:
    """Create SQLite engine for provided database path."""
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        make_sqlite_url(database_path),
        future=True,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create typed SQLAlchemy session factory."""
    return sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def create_default_session_factory() -> sessionmaker[Session]:
    """Create session factory using configured local database path."""
    return create_session_factory(create_sqlite_engine(get_database_path()))
