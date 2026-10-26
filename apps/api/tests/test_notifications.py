from uuid import uuid4

import pytest

from friday.domain.models import NotificationCreate
from friday.services.notifications import NotificationService
from friday.services.store import InMemoryStore


def test_notification_deduplicates_by_user_and_key():
    user_id = uuid4()
    service = NotificationService(InMemoryStore())
    payload = NotificationCreate(title="Task due", body="Review it", deduplication_key="task-1")
    assert service.create(user_id, payload).id == service.create(user_id, payload).id
    assert len(service.list_for_user(user_id)) == 1


def test_notification_redacts_secret_shaped_text():
    service = NotificationService(InMemoryStore())
    item = service.create(
        uuid4(),
        NotificationCreate(
            title="Provider alert",
            body="Token sk-project_abcdefghijklmnopqrstuvwxyz failed",
            deduplication_key="provider-1",
        ),
    )
    assert "sk-project" not in item.body
    assert "[REDACTED]" in item.body


def test_dismiss_hides_notification_and_audits():
    user_id = uuid4()
    store = InMemoryStore()
    service = NotificationService(store)
    item = service.create(
        user_id,
        NotificationCreate(title="Ready", body="Done", deduplication_key="done-1"),
    )
    service.dismiss(user_id, item.id)
    assert service.list_for_user(user_id) == []
    assert store.audit_events[-1].event_type == "notification.dismissed"


def test_cross_user_notification_access_is_denied():
    service = NotificationService(InMemoryStore())
    item = service.create(
        uuid4(), NotificationCreate(title="Private", body="Private", deduplication_key="p")
    )
    with pytest.raises(PermissionError):
        service.mark_read(uuid4(), item.id)

