from dataclasses import dataclass
from datetime import UTC, datetime
import secrets
from typing import Protocol
from urllib.parse import urlencode
from uuid import UUID

import httpx

from friday.domain.models import CredentialStatus, OAuthGrantMetadata


@dataclass(frozen=True, repr=False)
class OAuthTokenSet:
    access_token: str
    refresh_token: str
    expires_at: datetime
    scopes: set[str]


class TrustedTokenStore(Protocol):
    def load_refresh_token(self, credential_id: UUID) -> str: ...
    def replace_tokens(self, credential_id: UUID, tokens: OAuthTokenSet) -> None: ...


class OAuthProvider(Protocol):
    def refresh(self, refresh_token: str, scopes: set[str]) -> OAuthTokenSet: ...


class OAuthRotationService:
    """Trusted-only refresh flow. Token values never enter model-visible return types."""

    def __init__(self, store: TrustedTokenStore, providers: dict[str, OAuthProvider]) -> None:
        self.store = store
        self.providers = providers
        self.metadata: dict[UUID, OAuthGrantMetadata] = {}

    def register(self, metadata: OAuthGrantMetadata) -> None:
        self.metadata[metadata.credential_id] = metadata

    def ensure_fresh(self, credential_id: UUID) -> OAuthGrantMetadata:
        metadata = self.metadata[credential_id]
        if metadata.status != CredentialStatus.ACTIVE:
            raise PermissionError(f"OAuth grant is {metadata.status}")
        now = datetime.now(UTC)
        if metadata.access_expires_at > now:
            return metadata
        provider = self.providers.get(metadata.provider)
        if provider is None:
            raise RuntimeError("OAuth provider adapter is unavailable")
        try:
            refresh_token = self.store.load_refresh_token(credential_id)
            rotated = provider.refresh(refresh_token, metadata.scopes)
        except Exception as exc:
            metadata.status = CredentialStatus.EXPIRED
            raise RuntimeError("OAuth refresh failed; reauthentication is required") from exc
        if not rotated.scopes.issubset(metadata.scopes):
            metadata.status = CredentialStatus.REVOKED
            raise PermissionError("OAuth refresh attempted to expand scopes")
        self.store.replace_tokens(credential_id, rotated)
        metadata.scopes = rotated.scopes
        metadata.access_expires_at = rotated.expires_at
        metadata.refresh_rotated_at = now
        return metadata


class LinkedInOAuthService:
    authorize_endpoint = "https://www.linkedin.com/oauth/v2/authorization"
    token_endpoint = "https://www.linkedin.com/oauth/v2/accessToken"
    post_endpoint = "https://api.linkedin.com/v2/ugcPosts"
    userinfo_endpoint = "https://api.linkedin.com/v2/userinfo"

    def __init__(self, client_id: str | None, client_secret: str | None, redirect_uri: str) -> None:
        self.client_id = client_id
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.author_urn: str | None = None
        self._states: set[str] = set()
        self._access_token: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self._client_secret)

    @property
    def connected(self) -> bool:
        return self._access_token is not None

    def authorization_url(self) -> str:
        if not self.client_id:
            raise RuntimeError("LinkedIn client ID is not configured")
        state = secrets.token_urlsafe(32)
        self._states.add(state)
        return f"{self.authorize_endpoint}?{urlencode({'response_type': 'code', 'client_id': self.client_id, 'redirect_uri': self.redirect_uri, 'state': state, 'scope': 'openid profile w_member_social'})}"

    def configure(self, client_id: str, client_secret: str, redirect_uri: str, author_urn: str | None = None) -> None:
        if not client_id.strip() or not client_secret:
            raise ValueError("LinkedIn client ID and secret are required")
        if not redirect_uri.startswith("https://"):
            raise ValueError("LinkedIn redirect URI must use HTTPS")
        if author_urn and not author_urn.startswith("urn:li:person:"):
            raise ValueError("LinkedIn author must be a member URN")
        self.client_id = client_id.strip()
        self._client_secret = client_secret
        self.redirect_uri = redirect_uri.strip()
        self.author_urn = author_urn

    def exchange_code(self, code: str, state: str) -> None:
        if state not in self._states:
            raise PermissionError("Invalid or expired OAuth state")
        self._states.remove(state)
        if not self.configured:
            raise RuntimeError("LinkedIn credentials are not configured")
        response = httpx.post(
            self.token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": self.client_id,
                "client_secret": self._client_secret,
                "redirect_uri": self.redirect_uri,
            },
            timeout=20,
        )
        response.raise_for_status()
        self._access_token = response.json()["access_token"]
        identity = httpx.get(
            self.userinfo_endpoint,
            headers={"Authorization": f"Bearer {self._access_token}"},
            timeout=20,
        )
        identity.raise_for_status()
        member_id = identity.json().get("sub")
        if not member_id:
            self._access_token = None
            raise RuntimeError("LinkedIn did not return a member identity")
        self.author_urn = f"urn:li:person:{member_id}"

    def publish_text(self, author_urn: str, text: str) -> str:
        if not self._access_token:
            raise PermissionError("LinkedIn is not connected")
        if not author_urn.startswith("urn:li:person:"):
            raise ValueError("A valid LinkedIn member URN is required")
        response = httpx.post(
            self.post_endpoint,
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "X-Restli-Protocol-Version": "2.0.0",
                "Content-Type": "application/json",
            },
            json={
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": text},
                        "shareMediaCategory": "NONE",
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
                },
            },
            timeout=20,
        )
        response.raise_for_status()
        post_id = response.headers.get("x-restli-id")
        if not post_id:
            raise RuntimeError("LinkedIn did not return a post ID")
        return post_id
