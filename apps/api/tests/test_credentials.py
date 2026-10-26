from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from friday.domain.models import CredentialMetadata, CredentialStatus
from friday.services.credentials import CredentialBroker, DevelopmentSecretResolver
from friday.services.store import InMemoryStore


def broker_with_reference(metadata: CredentialMetadata):
    store = InMemoryStore()
    broker = CredentialBroker(store, DevelopmentSecretResolver({metadata.id}))
    broker.register(metadata)
    return broker, store


def test_capability_is_scope_limited_and_short_lived():
    metadata = CredentialMetadata(
        user_id=uuid4(), provider="github", account_label="Personal", scopes={"repo:read"}
    )
    broker, store = broker_with_reference(metadata)
    capability = broker.issue_capability(metadata.id, {"repo:read"}, uuid4(), 999)
    assert capability.allowed_scopes == {"repo:read"}
    assert capability.expires_at <= datetime.now(UTC) + timedelta(seconds=301)
    assert store.audit_events[-1].event_type == "credential.capability_issued"
    assert "secret" not in str(store.audit_events[-1].safe_payload).lower()


def test_scope_escalation_is_denied():
    metadata = CredentialMetadata(
        user_id=uuid4(), provider="github", account_label="Personal", scopes={"repo:read"}
    )
    broker, _ = broker_with_reference(metadata)
    with pytest.raises(PermissionError, match="exceeds"):
        broker.issue_capability(metadata.id, {"repo:write"}, uuid4())


def test_expired_credential_is_denied_and_marked_expired():
    metadata = CredentialMetadata(
        user_id=uuid4(),
        provider="gmail",
        account_label="Work",
        scopes={"mail:read"},
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    broker, _ = broker_with_reference(metadata)
    with pytest.raises(PermissionError, match="expired"):
        broker.issue_capability(metadata.id, {"mail:read"}, uuid4())
    assert metadata.status == CredentialStatus.EXPIRED


def test_revoked_credential_is_denied():
    metadata = CredentialMetadata(
        user_id=uuid4(), provider="calendar", account_label="Personal", scopes={"events:read"}
    )
    broker, _ = broker_with_reference(metadata)
    broker.revoke(metadata.id)
    with pytest.raises(PermissionError, match="revoked"):
        broker.issue_capability(metadata.id, {"events:read"}, uuid4())


def test_registration_requires_trusted_store_reference():
    metadata = CredentialMetadata(
        user_id=uuid4(), provider="github", account_label="Missing", scopes=set()
    )
    with pytest.raises(ValueError, match="trusted secret store"):
        CredentialBroker(InMemoryStore(), DevelopmentSecretResolver()).register(metadata)
