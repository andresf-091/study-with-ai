"""Smoke tests for Alembic migrations on a clean SQLite database."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_alembic_upgrade_head_on_clean_sqlite() -> None:
    db_path = Path("tests") / f"_runtime_migration_smoke_{uuid4().hex}.db"
    config = _make_alembic_config(db_path)

    try:
        command.upgrade(config, "head")

        engine = create_engine(_sqlite_url(db_path))
        try:
            table_names = set(inspect(engine).get_table_names())
        finally:
            engine.dispose()

        assert {
            "courses",
            "course_sources",
            "raw_texts",
            "modules",
            "deadlines",
            "llm_calls",
        }.issubset(table_names)
    finally:
        db_path.unlink(missing_ok=True)


def _make_alembic_config(db_path: Path) -> Config:
    config = Config(str(Path("alembic.ini").resolve()))
    config.set_main_option("script_location", str(Path("alembic").resolve()))
    config.set_main_option("sqlalchemy.url", _sqlite_url(db_path))
    return config


def _sqlite_url(db_path: Path) -> str:
    return f"sqlite:///{db_path.as_posix()}"
