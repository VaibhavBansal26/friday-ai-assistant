import re
from uuid import UUID

from friday.domain.models import (
    ActionRequest,
    ContentDraft,
    ContentDraftCreate,
    Provenance,
    PublicationEvidence,
    RiskLevel,
    VerificationResult,
)


PRIVATE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)password\s*[:=]\s*\S+"),
)


class ContentService:
    def __init__(self) -> None:
        self.drafts: dict[UUID, ContentDraft] = {}

    def create_draft(self, user_id: UUID, payload: ContentDraftCreate) -> ContentDraft:
        for claim in payload.claims:
            if claim.provenance in {Provenance.RETRIEVED, Provenance.VERIFIED}:
                if not claim.source_url or not claim.source_title:
                    raise ValueError("Research-based claims require a source URL and title")
            if claim.provenance == Provenance.UNKNOWN:
                raise ValueError("Unknown claims cannot be presented in publishable content")
        if any(pattern.search(payload.body) for pattern in PRIVATE_PATTERNS):
            raise ValueError("Draft appears to contain private or credential material")
        draft = ContentDraft(user_id=user_id, **payload.model_dump())
        self.drafts[draft.id] = draft
        return draft

    def publishing_action(self, user_id: UUID, draft_id: UUID) -> ActionRequest:
        draft = self.drafts[draft_id]
        if draft.user_id != user_id:
            raise PermissionError("Content draft belongs to another user")
        return ActionRequest(
            agent="publishing-agent",
            action="publish_content",
            target=f"{draft.platform}:{draft.target_account}",
            risk=RiskLevel.EXTERNAL_COMMUNICATION,
            data_transmitted=["title", "body", "assets", "citations"],
            reversible=True,
            expected_outcome="Platform returns a post ID, URL, and publication status",
            idempotency_key=f"publish:{draft.platform}:{draft.id}",
            preview=draft.model_dump(mode="json"),
        )

    @staticmethod
    def verify_publication(evidence: PublicationEvidence) -> VerificationResult:
        has_url = bool(evidence.public_url or evidence.scheduled_url)
        verified = bool(evidence.post_id and has_url and evidence.status in {"published", "scheduled"})
        missing: list[str] = []
        if not evidence.post_id:
            missing.append("post_id")
        if not has_url:
            missing.append("public_or_scheduled_url")
        if evidence.status not in {"published", "scheduled"}:
            missing.append("confirmed_publication_status")
        return VerificationResult(
            verified=verified,
            outcome="completed" if verified else "unverified",
            missing_evidence=missing,
        )

    def compose_linkedin_draft(
        self,
        user_id: UUID,
        topic: str,
        audience: str,
        key_points: list[str],
        call_to_action: str,
        target_account: str,
        tone: str = "clear",
    ) -> ContentDraft:
        topic = topic.strip()
        audience = audience.strip()
        points = [point.strip() for point in key_points if point.strip()]
        if not topic or not audience or not points:
            raise ValueError("Topic, audience, and at least one key point are required")
        if len(points) > 8:
            raise ValueError("LinkedIn drafts support at most eight key points")
        hooks = {
            "clear": f"A practical lesson about {topic}:",
            "bold": f"Most advice about {topic} misses the operational reality.",
            "reflective": f"I have been thinking differently about {topic}.",
        }
        if tone not in hooks:
            raise ValueError("Tone must be clear, bold, or reflective")
        body_parts = [hooks[tone], "", f"For {audience}, the useful takeaways are:", ""]
        body_parts.extend(f"• {point}" for point in points)
        body_parts.extend(
            [
                "",
                call_to_action.strip() or "What has worked in your experience?",
                "",
                "#ArtificialIntelligence #Productivity #FutureOfWork",
            ]
        )
        claims = [
            {
                "text": point,
                "provenance": Provenance.USER_PROVIDED,
            }
            for point in points
        ]
        return self.create_draft(
            user_id,
            ContentDraftCreate(
                platform="linkedin",
                title=topic[:300],
                body="\n".join(body_parts),
                claims=claims,
                target_account=target_account,
            ),
        )
