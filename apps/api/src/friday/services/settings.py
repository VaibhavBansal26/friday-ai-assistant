from uuid import UUID

from friday.domain.models import AuditEvent, UserSettings, UserSettingsUpdate, now_utc
from friday.services.store import InMemoryStore


class SettingsService:
    """User preferences only; security policy cannot be weakened through this service."""

    def __init__(self, audit_store: InMemoryStore) -> None:
        self.audit_store = audit_store
        self.values: dict[UUID, UserSettings] = {}

    def get(self, user_id: UUID) -> UserSettings:
        if user_id not in self.values:
            self.values[user_id] = UserSettings(user_id=user_id)
        return self.values[user_id]

    def update(self, user_id: UUID, payload: UserSettingsUpdate) -> UserSettings:
        settings = self.get(user_id)
        changed = payload.model_dump(exclude_unset=True)
        for key, value in changed.items():
            setattr(settings, key, value)
        settings.updated_at = now_utc()
        self.audit_store.append_audit(
            AuditEvent(
                user_id=user_id,
                event_type="settings.updated",
                actor="user",
                target_type="user_settings",
                target_id=str(user_id),
                safe_payload={"changed_fields": sorted(changed)},
            )
        )
        return settings

