from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from friday.domain.models import CredentialStatus, OAuthGrantMetadata
from friday.services.oauth import OAuthRotationService, OAuthTokenSet


class FakeStore:
    def __init__(self):
        self.loaded = "refresh-secret"
        self.replaced = None

    def load_refresh_token(self, credential_id):
        return self.loaded

    def replace_tokens(self, credential_id, tokens):
        self.replaced = (credential_id, tokens)


class FakeProvider:
    def __init__(self, scopes=None, fails=False):
        self.scopes = scopes or {"mail.read"}
        self.fails = fails

    def refresh(self, refresh_token, scopes):
        if self.fails:
            raise ValueError("provider leaked token refresh-secret")
        return OAuthTokenSet(
            access_token="new-access",
            refresh_token="new-refresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
            scopes=self.scopes,
        )


def metadata(scopes=None):
    return OAuthGrantMetadata(
        credential_id=uuid4(),
        provider="gmail",
        scopes=scopes or {"mail.read"},
        access_expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )


def test_expired_access_token_rotates_atomically_in_trusted_store():
    store = FakeStore()
    service = OAuthRotationService(store, {"gmail": FakeProvider()})
    item = metadata()
    service.register(item)
    result = service.ensure_fresh(item.credential_id)
    assert store.replaced[0] == item.credential_id
    assert result.refresh_rotated_at is not None
    assert "access_token" not in result.model_dump()


def test_refresh_cannot_expand_scopes():
    service = OAuthRotationService(
        FakeStore(), {"gmail": FakeProvider({"mail.read", "mail.send"})}
    )
    item = metadata({"mail.read"})
    service.register(item)
    with pytest.raises(PermissionError, match="expand scopes"):
        service.ensure_fresh(item.credential_id)
    assert item.status == CredentialStatus.REVOKED


def test_provider_failure_is_redacted_and_requires_reauthentication():
    service = OAuthRotationService(FakeStore(), {"gmail": FakeProvider(fails=True)})
    item = metadata()
    service.register(item)
    with pytest.raises(RuntimeError, match="reauthentication") as error:
        service.ensure_fresh(item.credential_id)
    assert "refresh-secret" not in str(error.value)
    assert item.status == CredentialStatus.EXPIRED


def test_fresh_grant_does_not_access_secret_store():
    store = FakeStore()
    service = OAuthRotationService(store, {"gmail": FakeProvider()})
    item = metadata()
    item.access_expires_at = datetime.now(UTC) + timedelta(minutes=10)
    service.register(item)
    service.ensure_fresh(item.credential_id)
    assert store.replaced is None
