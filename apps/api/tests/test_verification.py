from friday.domain.models import ActionRequest, RiskLevel, ToolEvidence
from friday.services.verification import VerificationEngine


def request(action: str) -> ActionRequest:
    return ActionRequest(
        agent="test",
        action=action,
        target="test-target",
        risk=RiskLevel.HIGH_IMPACT,
        reversible=False,
        expected_outcome="verified result",
        idempotency_key=f"key-{action}",
    )


def test_never_claims_completion_without_evidence():
    result = VerificationEngine().verify(request("create_pull_request"), [])
    assert not result.verified
    assert result.outcome == "failed"


def test_pr_requires_id_and_url():
    action = request("create_pull_request")
    evidence = ToolEvidence(action_id=action.id, provider="github", success=True, result_id="42")
    result = VerificationEngine().verify(action, [evidence])
    assert not result.verified
    assert "result_url" in result.missing_evidence


def test_pr_with_provider_evidence_is_verified():
    action = request("create_pull_request")
    evidence = ToolEvidence(
        action_id=action.id,
        provider="github",
        success=True,
        result_id="42",
        result_url="https://github.example/org/repo/pull/42",
        resulting_state="open",
    )
    assert VerificationEngine().verify(action, [evidence]).verified

