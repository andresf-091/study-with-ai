"""SQLAlchemy repository for course decomposition plan persistence."""

from __future__ import annotations

import json
from datetime import datetime
from typing import cast
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from praktikum_app.application.course_decomposition import (
    CoursePlanRepository,
    CourseRawTextRecord,
    SaveCoursePlanStats,
)
from praktikum_app.domain.course_plan import (
    CoursePlanCourse,
    CoursePlanDeadline,
    CoursePlanModule,
    CoursePlanV1,
)
from praktikum_app.infrastructure.db.models import (
    CourseModel,
    DeadlineModel,
    ModuleModel,
    RawTextModel,
)


class SqlAlchemyCoursePlanRepository(CoursePlanRepository):
    """Persist and load CoursePlan v1 using SQLAlchemy session."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_raw_text(
        self,
        course_id: str,
        raw_text_id: str | None = None,
    ) -> CourseRawTextRecord | None:
        if raw_text_id is not None:
            statement = select(RawTextModel).where(
                RawTextModel.course_id == course_id,
                RawTextModel.id == raw_text_id,
            )
        else:
            statement = (
                select(RawTextModel)
                .where(RawTextModel.course_id == course_id)
                .order_by(RawTextModel.created_at.desc())
                .limit(1)
            )

        raw_text_model = self._session.execute(statement).scalars().first()
        if raw_text_model is None:
            return None

        return CourseRawTextRecord(
            course_id=raw_text_model.course_id,
            raw_text_id=raw_text_model.id,
            content=raw_text_model.content,
            content_hash=raw_text_model.content_hash,
            length=raw_text_model.length,
        )

    def load_course_plan(self, course_id: str) -> CoursePlanV1 | None:
        course_model = self._session.get(CourseModel, course_id)
        if course_model is None:
            return None

        modules = list(
            self._session.execute(
                select(ModuleModel)
                .where(ModuleModel.course_id == course_id)
                .order_by(ModuleModel.position.asc())
            ).scalars()
        )
        if not modules:
            return None

        module_by_id_order: dict[str, int] = {}
        plan_modules: list[CoursePlanModule] = []
        for module_model in modules:
            module_by_id_order[module_model.id] = module_model.position
            plan_modules.append(
                CoursePlanModule(
                    order=module_model.position,
                    title=module_model.title,
                    goals=_read_json_list(module_model.goals_json),
                    topics=_read_json_list(module_model.topics_json),
                    estimated_hours=module_model.estimated_hours or 1,
                    submission_criteria=None,
                )
            )

        deadlines = list(
            self._session.execute(
                select(DeadlineModel)
                .where(DeadlineModel.course_id == course_id)
                .order_by(DeadlineModel.position.asc())
            ).scalars()
        )
        plan_deadlines: list[CoursePlanDeadline] = []
        for deadline_model in deadlines:
            if deadline_model.module_id is None:
                continue
            module_ref = module_by_id_order.get(deadline_model.module_id)
            if module_ref is None:
                continue

            plan_deadlines.append(
                CoursePlanDeadline(
                    order=deadline_model.position,
                    module_ref=module_ref,
                    due_at=deadline_model.due_at,
                    kind=deadline_model.kind,
                    notes=deadline_model.notes,
                )
            )

        return CoursePlanV1(
            schema_version="v1",
            course=CoursePlanCourse(
                title=course_model.title or "Курс",
                description=course_model.description or "Описание пока не заполнено.",
                start_date=course_model.start_date,
            ),
            modules=plan_modules,
            deadlines=plan_deadlines,
        )

    def replace_course_plan(
        self,
        course_id: str,
        plan: CoursePlanV1,
        saved_at: datetime,
    ) -> SaveCoursePlanStats:
        course_model = self._session.get(CourseModel, course_id)
        if course_model is None:
            raise ValueError("Course does not exist.")

        course_model.title = plan.course.title
        course_model.description = plan.course.description
        course_model.start_date = plan.course.start_date

        self._session.execute(delete(DeadlineModel).where(DeadlineModel.course_id == course_id))
        self._session.execute(delete(ModuleModel).where(ModuleModel.course_id == course_id))

        module_id_by_order: dict[int, str] = {}
        for module in plan.modules:
            module_id = str(uuid4())
            module_id_by_order[module.order] = module_id
            self._session.add(
                ModuleModel(
                    id=module_id,
                    course_id=course_id,
                    title=module.title,
                    position=module.order,
                    goals_json=json.dumps(module.goals, ensure_ascii=False),
                    topics_json=json.dumps(module.topics, ensure_ascii=False),
                    estimated_hours=module.estimated_hours,
                    status="planned",
                    created_at=saved_at,
                )
            )

        for deadline in plan.deadlines:
            module_id = module_id_by_order.get(deadline.module_ref)
            if module_id is None:
                raise ValueError(
                    f"Unknown module_ref={deadline.module_ref} for deadline order={deadline.order}."
                )

            self._session.add(
                DeadlineModel(
                    id=str(uuid4()),
                    course_id=course_id,
                    module_id=module_id,
                    position=deadline.order,
                    kind=deadline.kind,
                    notes=deadline.notes,
                    title=f"{deadline.kind} #{deadline.order}",
                    due_at=deadline.due_at,
                    status="planned",
                    created_at=saved_at,
                )
            )

        return SaveCoursePlanStats(
            modules_count=len(plan.modules),
            deadlines_count=len(plan.deadlines),
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
