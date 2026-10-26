from uuid import uuid4

from friday.domain.models import ActionRequest, Approval, ApprovalStatus, RiskLevel
from friday.services.policy import PolicyEngine


def action(risk: RiskLevel) -> ActionRequest:
    return ActionRequest(
        agent="test-agent",
        action="send_email",
        target="recipient@example.test",
        risk=risk,
        reversible=False,
        expected_outcome="Provider accepts one message",
        idempotency_key="test-1",
    )


def test_read_only_allowed_without_approval():
    assert PolicyEngine().evaluate(action(RiskLevel.READ_ONLY)).allowed


def test_external_write_denied_without_approval():
    result = PolicyEngine().evaluate(action(RiskLevel.EXTERNAL_COMMUNICATION))
    assert not result.allowed
    assert result.requires_approval


def test_mismatched_approval_is_denied():
    request = action(RiskLevel.HIGH_IMPACT)
    approval = Approval(action_id=uuid4(), status=ApprovalStatus.APPROVED_ONCE)
    assert not PolicyEngine().evaluate(request, approval).allowed


def test_matching_approval_is_allowed():
    request = action(RiskLevel.HIGH_IMPACT)
    approval = Approval(action_id=request.id, status=ApprovalStatus.APPROVED_ONCE)
    assert PolicyEngine().evaluate(request, approval).allowed

