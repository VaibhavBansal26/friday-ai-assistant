import pytest

from friday.domain.models import ActionRequest, RiskLevel
from friday.services.store import InMemoryStore


def make_action(key: str) -> ActionRequest:
    return ActionRequest(
        agent="email",
        action="send_email",
        target="test@example.test",
        risk=RiskLevel.EXTERNAL_COMMUNICATION,
        reversible=False,
        expected_outcome="one message accepted",
        idempotency_key=key,
    )


def test_duplicate_action_returns_same_approval():
    store = InMemoryStore()
    action = make_action("email-1")
    first = store.create_action(action)
    second = store.create_action(action)
    assert first == second


def test_key_cannot_be_reused_for_different_action():
    store = InMemoryStore()
    store.create_action(make_action("email-1"))
    with pytest.raises(ValueError, match="another action"):
        store.create_action(make_action("email-1"))

