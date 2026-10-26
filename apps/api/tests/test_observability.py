from decimal import Decimal
from uuid import uuid4

from friday.services.observability import EvaluationGate, TraceRecorder


def test_trace_redacts_credentials_and_accumulates_cost():
    recorder = TraceRecorder()
    event = recorder.record(
        uuid4(),
        "tool.completed",
        tool="provider",
        estimated_cost_usd=Decimal("0.012"),
        attributes={"api_key": "secret", "message": "token sk-project_abcdefghijklmnopqrstuvwxyz"},
    )
    assert event.safe_attributes["api_key"] == "[REDACTED]"
    assert "sk-project" not in event.safe_attributes["message"]
    assert recorder.total_cost == Decimal("0.012")


def test_empty_evaluation_samples_fail_closed():
    result = EvaluationGate().evaluate({})
    assert not result.releasable
    assert "unauthorized_action_rate" in result.blockers
    assert "verification_coverage" in result.blockers


def test_one_unauthorized_action_blocks_release():
    observations = {
        "unauthorized_action_rate": (1, 100),
        "hallucinated_completion_rate": (0, 100),
        "cross_user_leakage_rate": (0, 100),
        "credential_leakage_rate": (0, 100),
        "unsupported_resume_claim_rate": (0, 100),
        "verification_coverage": (100, 100),
    }
    result = EvaluationGate().evaluate(observations)
    assert not result.releasable
    assert result.blockers == ["unauthorized_action_rate"]


def test_perfect_critical_safety_metrics_pass_gate():
    observations = {
        "unauthorized_action_rate": (0, 100),
        "hallucinated_completion_rate": (0, 100),
        "cross_user_leakage_rate": (0, 100),
        "credential_leakage_rate": (0, 100),
        "unsupported_resume_claim_rate": (0, 100),
        "verification_coverage": (100, 100),
    }
    assert EvaluationGate().evaluate(observations).releasable
