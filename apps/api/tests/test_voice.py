from friday.domain.models import RiskLevel
from friday.services.voice import TranscriptValidator


def test_read_only_voice_request_needs_no_readback():
    result = TranscriptValidator().assess("List my tasks for today")
    assert result.risk == RiskLevel.READ_ONLY
    assert not result.requires_readback


def test_high_impact_voice_request_requires_readback():
    result = TranscriptValidator().assess("Submit the application to Acme using resume version four")
    assert result.risk == RiskLevel.HIGH_IMPACT
    assert result.requires_readback
    assert "Shall I proceed?" in result.readback


def test_ambiguous_consequential_request_is_blocked_for_clarification():
    result = TranscriptValidator().assess("Send something")
    assert result.risk == RiskLevel.EXTERNAL_COMMUNICATION
    assert result.ambiguous
    assert "unclear or missing target" in result.ambiguity_reasons


def test_destructive_voice_request_is_level_four():
    result = TranscriptValidator().assess("Delete the repository named archive")
    assert result.risk == RiskLevel.DESTRUCTIVE_OR_FINANCIAL

