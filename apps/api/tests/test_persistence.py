from uuid import uuid4

import pytest

from friday.core.config import Settings
from friday.domain.models import TaskCreate, TaskStatus, TaskUpdate
from friday.services.persistence import PersistenceService
from friday.services.store import InMemoryStore


@pytest.mark.asyncio
async def test_memory_persistence_task_and_audit_are_consistent():
    service = PersistenceService(Settings(_env_file=None), InMemoryStore())
    task = await service.create_task(TaskCreate(title="Persist safely"))
    updated = await service.update_task(task.id, TaskUpdate(status=TaskStatus.COMPLETED))
    assert updated.status == TaskStatus.COMPLETED
    assert [event.event_type for event in await service.list_audit_events()] == [
        "task.created",
        "task.updated"
    ]


@pytest.mark.asyncio
async def test_memory_persistence_unknown_task_fails():
    service = PersistenceService(Settings(_env_file=None), InMemoryStore())
    with pytest.raises(KeyError):
        await service.update_task(uuid4(), TaskUpdate(status=TaskStatus.COMPLETED))
