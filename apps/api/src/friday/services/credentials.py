from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from friday.domain.models import (
    AuditEvent,
    CredentialCapability,
    CredentialMetadata,
    CredentialStatus,
)
from friday.services.store import InMemoryStore


class SecretResolver(Protocol):
    """Trusted OS-keychain adapter. Implementations must never return secrets to models."""

    def exists(self, credential_id: UUID) -> bool: ...


class CredentialBroker:
    def __init__(self, audit_store: InMemoryStore, resolver: SecretResolver) -> None:
        self.audit_store = audit_store
        self.resolver = resolver
        self.metadata: dict[UUID, CredentialMetadata] = {}

    def register(self, metadata: CredentialMetadata) -> CredentialMetadata:
        if metadata.id in self.metadata:
            raise ValueError("Credential metadata already exists")
        if not self.resolver.exists(metadata.id):
            raise ValueError("Credential reference is not present in the trusted secret store")
        self.metadata[metadata.id] = metadata
        self._audit(metadata, "credential.registered", [])
        return metadata

    def issue_capability(
        self,
        credential_id: UUID,
        requested_scopes: set[str],
        task_id: UUID,
        ttl_seconds: int = 60,
    ) -> CredentialCapability:
        metadata = self.metadata[credential_id]
        now = datetime.now(UTC)
        if metadata.status != CredentialStatus.ACTIVE:
            raise PermissionError(f"Credential is {metadata.status}")
        if metadata.expires_at is not None and metadata.expires_at <= now:
            metadata.status = CredentialStatus.EXPIRED
            raise PermissionError("Credential is expired")
        if not requested_scopes.issubset(metadata.scopes):
            raise PermissionError("Requested scope exceeds credential grant")
        if not self.resolver.exists(credential_id):
            raise PermissionError("Credential is unavailable in the trusted secret store")
        metadata.last_accessed_at = now
        self._audit(metadata, "credential.capability_issued", sorted(requested_scopes))
        return CredentialCapability(
            credential_id=credential_id,
            provider=metadata.provider,
            allowed_scopes=requested_scopes,
            expires_at=now + timedelta(seconds=min(max(ttl_seconds, 1), 300)),
            task_id=task_id,
        )

    def revoke(self, credential_id: UUID) -> CredentialMetadata:
        metadata = self.metadata[credential_id]
        metadata.status = CredentialStatus.REVOKED
        self._audit(metadata, "credential.revoked", [])
        return metadata

    def list_safe_metadata(self, user_id: UUID) -> list[CredentialMetadata]:
        return [item for item in self.metadata.values() if item.user_id == user_id]

    def _audit(
        self, metadata: CredentialMetadata, event_type: str, requested_scopes: list[str]
    ) -> None:
        self.audit_store.append_audit(
            AuditEvent(
                user_id=metadata.user_id,
                event_type=event_type,
                actor="credential-broker",
                target_type="credential_metadata",
                target_id=str(metadata.id),
                safe_payload={
                    "provider": metadata.provider,
                    "requested_scopes": requested_scopes,
                },
            )
        )


class DevelopmentSecretResolver:
    """Reference-only test adapter. It stores IDs, never secret values."""

    def __init__(self, references: set[UUID] | None = None) -> None:
        self.references = references or set()

    def exists(self, credential_id: UUID) -> bool:
        return credential_id in self.references

