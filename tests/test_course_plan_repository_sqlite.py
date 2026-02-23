"""Persistence tests for CoursePlan save/load flows on SQLite."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from praktikum_app.application.course_decomposition import (
    GetCoursePlanUseCase,
    SaveCoursePlanCommand,
    SaveCoursePlanUseCase,
)
from praktikum_app.application.import_persistence import PersistImportedCourseUseCase
from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanDeadline,
    CoursePlanModule,
    CoursePlanV1,
)
from praktikum_app.domain.import_text import CourseSource, CourseSourceType, RawCourseText
from praktikum_app.infrastructure.db.base import Base
from praktikum_app.infrastructure.db.course_plan_unit_of_work import SqlAlchemyCoursePlanUnitOfWork
from praktikum_app.infrastructure.db.models import DeadlineModel, ModuleModel
from praktikum_app.infrastructure.db.session import create_session_factory, create_sqlite_engine
from praktikum_app.infrastructure.db.unit_of_work import SqlAlchemyImportUnitOfWork


def test_course_plan_save_and_load_roundtrip() -> None:
    db_path = Path("tests") / f"_runtime_course_plan_roundtrip_{uuid4().hex}.db"
    session_factory, engine, course_id = _seed_course(db_path)
    try:
        save_use_case = SaveCoursePlanUseCase(
            lambda: SqlAlchemyCoursePlanUnitOfWork(session_factory),
        )
        get_use_case = GetCoursePlanUseCase(
            lambda: SqlAlchemyCoursePlanUnitOfWork(session_factory),
        )

        save_use_case.execute(
            SaveCoursePlanCommand(
                course_id=course_id,
                plan=_build_plan(modules_count=2, deadlines_count=1),
            )
        )
        loaded_plan = get_use_case.execute(course_id)

        assert loaded_plan is not None
        assert loaded_plan.course.title == "Python Core"
        assert len(loaded_plan.modules) == 2
        assert len(loaded_plan.deadlines) == 1
        assert loaded_plan.modules[0].goals == ["Цель 1"]
        assert loaded_plan.deadlines[0].kind == "проверка"
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_course_plan_save_is_idempotent_without_duplicates() -> None:
    db_path = Path("tests") / f"_runtime_course_plan_idempotent_{uuid4().hex}.db"
    session_factory, engine, course_id = _seed_course(db_path)
    try:
        save_use_case = SaveCoursePlanUseCase(
            lambda: SqlAlchemyCoursePlanUnitOfWork(session_factory),
        )
        command = SaveCoursePlanCommand(
            course_id=course_id,
            plan=_build_plan(modules_count=3, deadlines_count=2),
        )

        save_use_case.execute(command)
        save_use_case.execute(command)

        with session_factory() as session:
            modules_count = session.execute(
                select(func.count())
                .select_from(ModuleModel)
                .where(ModuleModel.course_id == course_id)
            ).scalar_one()
            deadlines_count = session.execute(
                select(func.count())
                .select_from(DeadlineModel)
                .where(DeadlineModel.course_id == course_id)
            ).scalar_one()

        assert modules_count == 3
        assert deadlines_count == 2
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def test_course_plan_save_with_no_deadlines_clears_previous_deadlines() -> None:
    db_path = Path("tests") / f"_runtime_course_plan_missing_deadlines_{uuid4().hex}.db"
    session_factory, engine, course_id = _seed_course(db_path)
    try:
        save_use_case = SaveCoursePlanUseCase(
            lambda: SqlAlchemyCoursePlanUnitOfWork(session_factory),
        )
        save_use_case.execute(
            SaveCoursePlanCommand(
                course_id=course_id,
                plan=_build_plan(modules_count=2, deadlines_count=2),
            )
        )
        save_use_case.execute(
            SaveCoursePlanCommand(
                course_id=course_id,
                plan=_build_plan(modules_count=2, deadlines_count=0),
            )
        )

        with session_factory() as session:
            deadlines_count = session.execute(
                select(func.count())
                .select_from(DeadlineModel)
                .where(DeadlineModel.course_id == course_id)
            ).scalar_one()

        assert deadlines_count == 0
    finally:
        engine.dispose()
        db_path.unlink(missing_ok=True)


def _seed_course(database_path: Path) -> tuple[sessionmaker[Session], Engine, str]:
    engine = create_sqlite_engine(database_path)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    persist_use_case = PersistImportedCourseUseCase(
        lambda: SqlAlchemyImportUnitOfWork(session_factory),
    )
    content = "Содержимое курса"
    raw_text = RawCourseText(
        content=content,
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        length=len(content),
        source=CourseSource(
            source_type=CourseSourceType.PASTE,
            filename=None,
            imported_at=datetime(2026, 2, 23, 10, 0, tzinfo=UTC),
        ),
    )
    saved = persist_use_case.execute(raw_text)
    return session_factory, engine, saved.course_id


def _build_plan(modules_count: int, deadlines_count: int) -> CoursePlanV1:
    modules: list[CoursePlanModule] = []
    for index in range(1, modules_count + 1):
        modules.append(
            CoursePlanModule(
                order=index,
                title=f"Модуль {index}",
                goals=[f"Цель {index}"],
                topics=[f"Тема {index}"],
                estimated_hours=4,
            )
        )

    deadlines: list[CoursePlanDeadline] = []
    for index in range(1, deadlines_count + 1):
        deadlines.append(
            CoursePlanDeadline(
                order=index,
                module_ref=1 if modules else index,
                due_at=datetime(2026, 3, index, 12, 0, tzinfo=UTC),
                kind="проверка",
                notes=f"Дедлайн {index}",
            )
        )

    return CoursePlanV1(
        course=CoursePlanCourse(
            title="Python Core",
            description="Детальный план курса",
            start_date=date(2026, 3, 1),
        ),
        modules=modules,
        deadlines=deadlines,
    )
