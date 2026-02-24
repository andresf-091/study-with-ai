"""Repository tests for practice generation persistence on SQLite."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.practice_generation import PracticeTaskDraft
from praktikum_app.domain.practice import PracticeDifficulty
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.models import CourseModel, ModuleModel
from praktikum_app.infrastructure.db.practice_unit_of_work import SqlAlchemyPracticeUnitOfWork
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine


def test_practice_repository_loads_module_context_and_modules_list() -> None:
    db_path = Path("tests") / f"_runtime_practice_context_{uuid4().hex}.db"
    session_factory, engine, course_id, module_id = _seed_course_with_module(db_path)
    try:
        with SqlAlchemyPracticeUnitOfWork(session_factory) as uow:
            context = uow.practice.get_module_context(module_id)
            modules = uow.practice.list_modules_for_course(course_id)

        assert context is not None
        assert context.module_id == module_id
        assert context.module_title == "Асинхронность"
        assert context.goals == ["Понять event loop"]
        assert context.topics == ["async", "await"]
        assert len(modules) == 1
        assert modules[0].module_id == module_id
        assert modules[0].module_order == 1
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_practice_repository_save_batch_and_read_current_task() -> None:
    db_path = Path("tests") / f"_runtime_practice_current_{uuid4().hex}.db"
    session_factory, engine, _, module_id = _seed_course_with_module(db_path)
    try:
        with SqlAlchemyPracticeUnitOfWork(session_factory) as uow:
            context = uow.practice.get_module_context(module_id)
            assert context is not None
            uow.practice.save_generated_batch(
                module_context=context,
                difficulty=PracticeDifficulty.MEDIUM,
                llm_call_id="llm-call-1",
                generation_id="generation-1",
                created_at=datetime(2026, 3, 2, 10, 0, tzinfo=UTC),
                candidates=[
                    PracticeTaskDraft(
                        candidate_index=1,
                        statement="Соберите ETL-пайплайн",
                        expected_outline="Функции, обработка ошибок, тесты",
                    ),
                    PracticeTaskDraft(
                        candidate_index=2,
                        statement="Сделайте асинхронный воркер",
                        expected_outline="Очередь задач, asyncio, retries",
                    ),
                ],
            )
            uow.commit()

        with SqlAlchemyPracticeUnitOfWork(session_factory) as uow:
            current = uow.practice.get_current_task(module_id)
            history = uow.practice.list_task_history(module_id)

        assert current is not None
        assert current.statement == "Соберите ETL-пайплайн"
        assert current.candidate_index == 1
        assert current.llm_call_id == "llm-call-1"
        assert len(history) == 2
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_practice_repository_regenerate_appends_history_without_overwrite() -> None:
    db_path = Path("tests") / f"_runtime_practice_history_{uuid4().hex}.db"
    session_factory, engine, _, module_id = _seed_course_with_module(db_path)
    try:
        with SqlAlchemyPracticeUnitOfWork(session_factory) as uow:
            context = uow.practice.get_module_context(module_id)
            assert context is not None
            uow.practice.save_generated_batch(
                module_context=context,
                difficulty=PracticeDifficulty.EASY,
                llm_call_id="llm-call-1",
                generation_id="generation-1",
                created_at=datetime(2026, 3, 2, 10, 0, tzinfo=UTC),
                candidates=[
                    PracticeTaskDraft(
                        candidate_index=1,
                        statement="Задание 1.1",
                        expected_outline="outline 1.1",
                    ),
                    PracticeTaskDraft(
                        candidate_index=2,
                        statement="Задание 1.2",
                        expected_outline="outline 1.2",
                    ),
                ],
            )
            uow.practice.save_generated_batch(
                module_context=context,
                difficulty=PracticeDifficulty.HARD,
                llm_call_id="llm-call-2",
                generation_id="generation-2",
                created_at=datetime(2026, 3, 2, 10, 5, tzinfo=UTC),
                candidates=[
                    PracticeTaskDraft(
                        candidate_index=1,
                        statement="Задание 2.1",
                        expected_outline="outline 2.1",
                    ),
                    PracticeTaskDraft(
                        candidate_index=2,
                        statement="Задание 2.2",
                        expected_outline="outline 2.2",
                    ),
                ],
            )
            uow.commit()

        with SqlAlchemyPracticeUnitOfWork(session_factory) as uow:
            current = uow.practice.get_current_task(module_id)
            history = uow.practice.list_task_history(module_id)

        assert current is not None
        assert current.statement == "Задание 2.1"
        assert current.generation_id == "generation-2"
        assert len(history) == 4
        assert {item.generation_id for item in history} == {"generation-1", "generation-2"}
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def _seed_course_with_module(
    database_path: Path,
) -> tuple[sessionmaker[Session], Engine, str, str]:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)
    course_id = "course-1"
    module_id = "module-1"

    with session_factory() as session:
        session.add(
            CourseModel(
                id=course_id,
                title="Python Advanced",
                created_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
            )
        )
        session.add(
            ModuleModel(
                id=module_id,
                course_id=course_id,
                title="Асинхронность",
                position=1,
                goals_json=json.dumps(["Понять event loop"], ensure_ascii=False),
                topics_json=json.dumps(["async", "await"], ensure_ascii=False),
                estimated_hours=6,
                status="planned",
                created_at=datetime(2026, 3, 1, 12, 5, tzinfo=UTC),
            )
        )
        session.commit()

    return session_factory, engine, course_id, module_id
