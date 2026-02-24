"""SQLAlchemy repository for generated practice tasks and module context."""

from __future__ import annotations

import json
from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from praktikum_app.application.practice_generation import (
    PracticeModuleContext,
    PracticeModuleSummary,
    PracticeRepository,
    PracticeTaskDraft,
)
from praktikum_app.domain.practice import PracticeDifficulty, PracticeTask
from praktikum_app.infrastructure.db.models import (
    CourseModel,
    ModuleModel,
    PracticeTaskModel,
)


class SqlAlchemyPracticeRepository(PracticeRepository):
    """Persist practice candidates and read module context via SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_module_context(self, module_id: str) -> PracticeModuleContext | None:
        row = self._session.execute(
            select(ModuleModel, CourseModel)
            .join(CourseModel, ModuleModel.course_id == CourseModel.id)
            .where(ModuleModel.id == module_id)
        ).first()
        if row is None:
            return None

        module_model, course_model = row
        return PracticeModuleContext(
            module_id=module_model.id,
            course_id=module_model.course_id,
            course_title=course_model.title,
            module_title=module_model.title,
            module_order=module_model.position,
            goals=_read_json_list(module_model.goals_json),
            topics=_read_json_list(module_model.topics_json),
            estimated_hours=module_model.estimated_hours,
        )

    def list_modules_for_course(self, course_id: str) -> list[PracticeModuleSummary]:
        modules = list(
            self._session.execute(
                select(ModuleModel)
                .where(ModuleModel.course_id == course_id)
                .order_by(ModuleModel.position.asc())
            ).scalars()
        )

        return [
            PracticeModuleSummary(
                module_id=module.id,
                course_id=module.course_id,
                module_order=module.position,
                module_title=module.title,
            )
            for module in modules
        ]

    def save_generated_batch(
        self,
        *,
        module_context: PracticeModuleContext,
        difficulty: PracticeDifficulty,
        llm_call_id: str,
        generation_id: str,
        created_at: datetime,
        candidates: list[PracticeTaskDraft],
    ) -> list[PracticeTask]:
        saved: list[PracticeTask] = []
        for candidate in candidates:
            model = PracticeTaskModel(
                id=str(uuid4()),
                course_id=module_context.course_id,
                module_id=module_context.module_id,
                llm_call_id=llm_call_id,
                generation_id=generation_id,
                candidate_index=candidate.candidate_index,
                difficulty=difficulty.value,
                statement=candidate.statement,
                expected_outline=candidate.expected_outline,
                created_at=created_at,
            )
            self._session.add(model)
            saved.append(_to_domain(model))

        saved.sort(key=lambda task: task.candidate_index)
        return saved

    def get_current_task(self, module_id: str) -> PracticeTask | None:
        latest_generation_id = self._session.execute(
            select(PracticeTaskModel.generation_id)
            .where(PracticeTaskModel.module_id == module_id)
            .order_by(PracticeTaskModel.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_generation_id is None:
            return None

        current_model = self._session.execute(
            select(PracticeTaskModel)
            .where(
                PracticeTaskModel.module_id == module_id,
                PracticeTaskModel.generation_id == latest_generation_id,
            )
            .order_by(PracticeTaskModel.candidate_index.asc())
            .limit(1)
        ).scalars().first()
        if current_model is None:
            return None

        return _to_domain(current_model)

    def list_task_history(self, module_id: str) -> list[PracticeTask]:
        models = list(
            self._session.execute(
                select(PracticeTaskModel)
                .where(PracticeTaskModel.module_id == module_id)
                .order_by(
                    PracticeTaskModel.created_at.desc(),
                    PracticeTaskModel.candidate_index.asc(),
                )
            ).scalars()
        )
        return [_to_domain(model) for model in models]


def _to_domain(model: PracticeTaskModel) -> PracticeTask:
    return PracticeTask(
        id=model.id,
        course_id=model.course_id,
        module_id=model.module_id,
        difficulty=PracticeDifficulty(model.difficulty),
        statement=model.statement,
        expected_outline=model.expected_outline,
        candidate_index=model.candidate_index,
        created_at=model.created_at,
        generation_id=model.generation_id,
        llm_call_id=model.llm_call_id,
    )


def _read_json_list(value: str) -> list[str]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(payload, list):
        return []

    items: list[str] = []
    for item in cast(list[object], payload):
        if isinstance(item, str):
            items.append(item)
    return items
