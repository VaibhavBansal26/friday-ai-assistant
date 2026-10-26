import re
from datetime import UTC, datetime, timedelta
from typing import Protocol

from friday.domain.models import (
    RealtimeSessionDescriptor,
    RiskLevel,
    VoiceTranscriptAssessment,
)


CONSEQUENTIAL_PATTERNS = {
    RiskLevel.EXTERNAL_COMMUNICATION: (
        r"\b(send|email|message|publish|post|comment)\b",
    ),
    RiskLevel.HIGH_IMPACT: (
        r"\b(submit|apply|push|deploy|merge|create (a )?pull request)\b",
    ),
    RiskLevel.DESTRUCTIVE_OR_FINANCIAL: (
        r"\b(delete|force push|purchase|buy|pay|cancel subscription)\b",
    ),
}
AMBIGUITY_MARKERS = ("[inaudible]", "[unclear]", "???", " something ", " someone ")


class TranscriptValidator:
    def assess(self, transcript: str) -> VoiceTranscriptAssessment:
        normalized = " ".join(transcript.strip().split())
        lowered = f" {normalized.lower()} "
        risk = RiskLevel.READ_ONLY
        for level, patterns in CONSEQUENTIAL_PATTERNS.items():
            if any(re.search(pattern, lowered) for pattern in patterns):
                risk = max(risk, level)
        reasons: list[str] = []
        if not normalized:
            reasons.append("empty transcript")
        if any(marker in lowered for marker in AMBIGUITY_MARKERS):
            reasons.append("unclear or missing target")
        if risk >= RiskLevel.EXTERNAL_COMMUNICATION and len(normalized.split()) < 4:
            reasons.append("consequential request lacks sufficient detail")
        requires_readback = risk >= RiskLevel.HIGH_IMPACT
        readback = None
        if requires_readback:
            readback = f'You asked me to: “{normalized}”. Shall I proceed?'
        return VoiceTranscriptAssessment(
            transcript=transcript,
            normalized_transcript=normalized,
            risk=risk,
            ambiguous=bool(reasons),
            ambiguity_reasons=reasons,
            requires_readback=requires_readback,
            readback=readback,
        )


class RealtimeSessionBroker(Protocol):
    async def create(self, model: str) -> RealtimeSessionDescriptor: ...


class DevelopmentRealtimeSessionBroker:
    """Non-network development broker; secrets are placeholders and never usable."""

    async def create(self, model: str) -> RealtimeSessionDescriptor:
        return RealtimeSessionDescriptor(
            session_id="development-disabled",
            provider="disabled",
            model=model,
            client_secret="not-a-credential",
            expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )

