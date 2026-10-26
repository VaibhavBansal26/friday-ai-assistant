from datetime import UTC, datetime, timedelta
from uuid import uuid4

from friday.domain.models import Session
from friday.services.local_auth import LocalSessionAuth


def session(expires_in=60):
    return Session(
        user_id=uuid4(),
        expires_at=datetime.now(UTC) + timedelta(seconds=expires_in),
    )


def test_session_token_is_opaque_and_only_hash_is_stored():
    auth = LocalSessionAuth()
    grant = auth.issue(session())
    assert len(grant.token) >= 32
    assert grant.token.encode() not in auth.token_hashes.values()
    assert auth.verify(grant.session.id, grant.token)


def test_wrong_token_is_rejected():
    auth = LocalSessionAuth()
    grant = auth.issue(session())
    assert not auth.verify(grant.session.id, "wrong-token")


def test_expired_session_is_rejected():
    auth = LocalSessionAuth()
    grant = auth.issue(session(-1))
    assert not auth.verify(grant.session.id, grant.token)


def test_revoked_session_is_rejected():
    auth = LocalSessionAuth()
    grant = auth.issue(session())
    auth.revoke(grant.session.id)
    assert not auth.verify(grant.session.id, grant.token)
