"""Database configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_FILENAME = "study_with_ai.db"
DB_PATH_ENV_VAR = "PRAKTIKUM_DB_PATH"


def get_database_path() -> Path:
    """Return configured SQLite database path."""
    configured = os.environ.get(DB_PATH_ENV_VAR)
    if configured:
        return Path(configured).expanduser().resolve()

    return (Path.home() / ".study-with-ai" / DEFAULT_DB_FILENAME).resolve()


def make_sqlite_url(database_path: Path) -> str:
    """Build SQLAlchemy SQLite URL from path."""
    return f"sqlite:///{database_path.as_posix()}"
