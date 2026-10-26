from uuid import UUID

from friday.core.redaction import redact
from friday.domain.models import AuditEvent, Notification, NotificationCreate
from friday.services.store import InMemoryStore


class NotificationService:
    def __init__(self, audit_store: InMemoryStore) -> None:
        self.audit_store = audit_store
        self.notifications: dict[UUID, Notification] = {}
        self.deduplication: dict[tuple[UUID, str], UUID] = {}

    def create(self, user_id: UUID, payload: NotificationCreate) -> Notification:
        key = (user_id, payload.deduplication_key)
        existing_id = self.deduplication.get(key)
        if existing_id is not None:
            return self.notifications[existing_id]
        safe = redact(payload.model_dump())
        notification = Notification(user_id=user_id, **safe)
        self.notifications[notification.id] = notification
        self.deduplication[key] = notification.id
        self._audit(notification, "notification.created")
        return notification

    def list_for_user(self, user_id: UUID, include_dismissed: bool = False) -> list[Notification]:
        return sorted(
            (
                item
                for item in self.notifications.values()
                if item.user_id == user_id and (include_dismissed or not item.dismissed)
            ),
            key=lambda item: item.created_at,
            reverse=True,
        )

    def mark_read(self, user_id: UUID, notification_id: UUID) -> Notification:
        notification = self._owned(user_id, notification_id)
        notification.read = True
        self._audit(notification, "notification.read")
        return notification

    def dismiss(self, user_id: UUID, notification_id: UUID) -> Notification:
        notification = self._owned(user_id, notification_id)
        notification.dismissed = True
        notification.read = True
        self._audit(notification, "notification.dismissed")
        return notification

    def _owned(self, user_id: UUID, notification_id: UUID) -> Notification:
        notification = self.notifications[notification_id]
        if notification.user_id != user_id:
            raise PermissionError("Notification belongs to another user")
        return notification

    def _audit(self, notification: Notification, event_type: str) -> None:
        self.audit_store.append_audit(
            AuditEvent(
                user_id=notification.user_id,
                event_type=event_type,
                actor="notification-agent",
                target_type="notification",
                target_id=str(notification.id),
                safe_payload={"category": notification.category},
            )
        )

