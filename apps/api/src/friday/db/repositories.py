from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from friday.db.models import AuditEventRow, TaskRow
from friday.domain.models import (
    AuditEvent,
    Task,
    TaskCreate,
    TaskPriority,
    TaskStatus,
    TaskUpdate,
    now_utc,
)


def task_from_row(row: TaskRow) -> Task:
    return Task(
        id=row.id,
        user_id=row.user_id,
        title=row.title,
        description=row.description,
        status=TaskStatus(row.status),
        priority=TaskPriority(row.priority),
        category=row.category,
        completion_criteria=row.completion_criteria,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresTaskRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user_id: UUID, payload: TaskCreate) -> Task:
        timestamp = now_utc()
        row = TaskRow(
            user_id=user_id,
            title=payload.title,
            description=payload.description,
            priority=payload.priority.value,
            category=payload.category,
            completion_criteria=payload.completion_criteria,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.session.add(row)
        await self.session.flush()
        return task_from_row(row)

    async def list_for_user(self, user_id: UUID) -> list[Task]:
        result = await self.session.scalars(
            select(TaskRow).where(TaskRow.user_id == user_id).order_by(TaskRow.created_at)
        )
        return [task_from_row(row) for row in result]

    async def update(self, user_id: UUID, task_id: UUID, payload: TaskUpdate) -> Task:
        row = await self.session.scalar(
            select(TaskRow).where(TaskRow.id == task_id, TaskRow.user_id == user_id)
        )
        if row is None:
            raise KeyError(task_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value.value if hasattr(value, "value") else value)
        row.updated_at = now_utc()
        await self.session.flush()
        return task_from_row(row)


class PostgresAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, event: AuditEvent) -> AuditEvent:
        self.session.add(
            AuditEventRow(
                id=event.id,
                user_id=event.user_id,
                session_id=event.session_id,
                event_type=event.event_type,
                actor=event.actor,
                target_type=event.target_type,
                target_id=event.target_id,
                safe_payload=event.safe_payload,
                created_at=event.created_at,
            )
        )
        await self.session.flush()
        return event

