from uuid import uuid4

from friday.domain.models import PrivacyPreference, UserSettingsUpdate
from friday.services.settings import SettingsService
from friday.services.store import InMemoryStore


def test_security_defaults_are_locked():
    settings = SettingsService(InMemoryStore()).get(uuid4())
    assert not settings.external_writes_enabled
    assert settings.memory_writes_require_approval


def test_user_can_update_preferences_but_not_external_write_authority():
    user_id = uuid4()
    store = InMemoryStore()
    service = SettingsService(store)
    settings = service.update(
        user_id,
        UserSettingsUpdate(
            privacy_preference=PrivacyPreference.LOCAL_ONLY,
            voice_speed=1.25,
        ),
    )
    assert settings.privacy_preference == PrivacyPreference.LOCAL_ONLY
    assert settings.voice_speed == 1.25
    assert not settings.external_writes_enabled
    assert store.audit_events[-1].safe_payload["changed_fields"] == [
        "privacy_preference",
        "voice_speed",
    ]
