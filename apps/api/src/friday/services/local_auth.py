import hashlib
import hmac
import secrets
from datetime import UTC, datetime
from uuid import UUID

from friday.domain.models import Session, SessionGrant


class LocalSessionAuth:
    """Issues opaque desktop-session tokens and stores only their hashes."""

    def __init__(self) -> None:
        self.token_hashes: dict[UUID, bytes] = {}
        self.sessions: dict[UUID, Session] = {}

    def issue(self, session: Session) -> SessionGrant:
        token = secrets.token_urlsafe(32)
        self.token_hashes[session.id] = self._hash(token)
        self.sessions[session.id] = session
        return SessionGrant(session=session, token=token)

    def verify(self, session_id: UUID, token: str) -> bool:
        session = self.sessions.get(session_id)
        expected = self.token_hashes.get(session_id)
        if session is None or expected is None or session.expires_at <= datetime.now(UTC):
            return False
        return hmac.compare_digest(expected, self._hash(token))

    def revoke(self, session_id: UUID) -> None:
        self.token_hashes.pop(session_id, None)
        self.sessions.pop(session_id, None)

    @staticmethod
    def _hash(token: str) -> bytes:
        return hashlib.sha256(token.encode()).digest()


local_session_auth = LocalSessionAuth()

