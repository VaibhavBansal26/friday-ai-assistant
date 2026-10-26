from uuid import UUID

from sqlalchemy import select

from friday.core.config import Settings
from friday.db.models import AuditEventRow
from friday.db.repositories import PostgresAuditRepository, PostgresTaskRepository
from friday.db.session import session_factory
from friday.domain.models import AuditEvent, Task, TaskCreate, TaskUpdate
from friday.services.store import InMemoryStore


def audit_from_row(row: AuditEventRow) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        user_id=row.user_id,
        session_id=row.session_id,
        event_type=row.event_type,
        actor=row.actor,
        target_type=row.target_type,
        target_id=row.target_id,
        safe_payload=row.safe_payload,
        created_at=row.created_at,
    )


class PersistenceService:
    """Selects memory or PostgreSQL without leaking storage details into API handlers."""

    def __init__(self, settings: Settings, memory: InMemoryStore) -> None:
        self.settings = settings
        self.memory = memory

    @property
    def uses_postgres(self) -> bool:
        return self.settings.persistence_backend == "postgresql"

    async def create_task(self, payload: TaskCreate) -> Task:
        if not self.uses_postgres:
            task = self.memory.create_task(payload)
            self.memory.append_audit(
                AuditEvent(
                    event_type="task.created",
                    actor="user",
                    target_type="task",
                    target_id=str(task.id),
                    safe_payload={"title": task.title, "priority": task.priority},
                )
            )
            return task
        async with session_factory.begin() as session:
            repository = PostgresTaskRepository(session)
            task = await repository.create(self.settings.local_user_id, payload)
            await PostgresAuditRepository(session).append(
                AuditEvent(
                    user_id=self.settings.local_user_id,
                    event_type="task.created",
                    actor="user",
                    target_type="task",
                    target_id=str(task.id),
                    safe_payload={"title": task.title, "priority": task.priority},
                )
            )
            return task

    async def list_tasks(self) -> list[Task]:
        if not self.uses_postgres:
            return list(self.memory.tasks.values())
        async with session_factory() as session:
            return await PostgresTaskRepository(session).list_for_user(
                self.settings.local_user_id
            )

    async def update_task(self, task_id: UUID, payload: TaskUpdate) -> Task:
        if not self.uses_postgres:
            task = self.memory.update_task(task_id, payload)
            self.memory.append_audit(
                AuditEvent(
                    event_type="task.updated",
                    actor="user",
                    target_type="task",
                    target_id=str(task.id),
                    safe_payload={"changed_fields": sorted(payload.model_fields_set)},
                )
            )
            return task
        async with session_factory.begin() as session:
            task = await PostgresTaskRepository(session).update(
                self.settings.local_user_id, task_id, payload
            )
            await PostgresAuditRepository(session).append(
                AuditEvent(
                    user_id=self.settings.local_user_id,
                    event_type="task.updated",
                    actor="user",
                    target_type="task",
                    target_id=str(task.id),
                    safe_payload={"changed_fields": sorted(payload.model_fields_set)},
                )
            )
            return task

    async def list_audit_events(self) -> list[AuditEvent]:
        if not self.uses_postgres:
            return list(self.memory.audit_events)
        async with session_factory() as session:
            result = await session.scalars(
                select(AuditEventRow)
                .where(AuditEventRow.user_id == self.settings.local_user_id)
                .order_by(AuditEventRow.created_at.desc())
            )
            return [audit_from_row(row) for row in result]
