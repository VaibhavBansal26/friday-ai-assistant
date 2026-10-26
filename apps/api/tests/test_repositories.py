from datetime import UTC, datetime
from uuid import uuid4

from friday.db.models import TaskRow
from friday.db.repositories import task_from_row
from friday.domain.models import TaskPriority, TaskStatus


def test_task_row_mapping_preserves_typed_state():
    now = datetime.now(UTC)
    row = TaskRow(
        id=uuid4(),
        user_id=uuid4(),
        title="Persist me",
        description=None,
        status="in_progress",
        priority="high",
        category="project",
        completion_criteria=["row exists"],
        created_at=now,
        updated_at=now,
    )
    task = task_from_row(row)
    assert task.status == TaskStatus.IN_PROGRESS
    assert task.priority == TaskPriority.HIGH
    assert task.user_id == row.user_id

