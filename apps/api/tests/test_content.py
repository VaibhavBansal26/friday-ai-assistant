from uuid import uuid4

import pytest

from friday.domain.models import (
    ContentClaim,
    ContentDraftCreate,
    ContentPlatform,
    Provenance,
    PublicationEvidence,
    RiskLevel,
)
from friday.services.content import ContentService


def payload(**changes):
    values = {
        "platform": ContentPlatform.LINKEDIN,
        "title": "Reliable agents",
        "body": "Reliable agents verify consequential actions.",
        "target_account": "personal",
        "claims": [],
    }
    values.update(changes)
    return ContentDraftCreate(**values)


def test_research_claim_requires_real_source_metadata():
    claim = ContentClaim(text="Agents improve outcomes", provenance=Provenance.RETRIEVED)
    with pytest.raises(ValueError, match="source URL and title"):
        ContentService().create_draft(uuid4(), payload(claims=[claim]))


def test_unknown_claim_cannot_enter_publishable_draft():
    claim = ContentClaim(text="Unknown statistic", provenance=Provenance.UNKNOWN)
    with pytest.raises(ValueError, match="Unknown claims"):
        ContentService().create_draft(uuid4(), payload(claims=[claim]))


def test_secret_shaped_content_is_rejected():
    with pytest.raises(ValueError, match="private or credential"):
        ContentService().create_draft(
            uuid4(), payload(body="Use token sk-project_abcdefghijklmnopqrstuvwxyz")
        )


def test_publish_is_level_two_preview_and_draft_remains_local():
    service = ContentService()
    user_id = uuid4()
    draft = service.create_draft(user_id, payload())
    action = service.publishing_action(user_id, draft.id)
    assert action.risk == RiskLevel.EXTERNAL_COMMUNICATION
    assert action.action == "publish_content"
    assert draft.status == "draft"


def test_publication_requires_id_url_and_status():
    result = ContentService.verify_publication(
        PublicationEvidence(platform=ContentPlatform.LINKEDIN, post_id="post-1")
    )
    assert not result.verified
    assert "public_or_scheduled_url" in result.missing_evidence
    assert "confirmed_publication_status" in result.missing_evidence


def test_complete_publication_evidence_is_verified():
    result = ContentService.verify_publication(
        PublicationEvidence(
            platform=ContentPlatform.LINKEDIN,
            post_id="post-1",
            public_url="https://example.test/posts/1",
            status="published",
        )
    )
    assert result.verified


def test_local_linkedin_composer_creates_publishable_editable_draft():
    service = ContentService()
    draft = service.compose_linkedin_draft(
        uuid4(),
        topic="reliable AI assistants",
        audience="product leaders",
        key_points=["Verify outcomes", "Pause before consequential actions"],
        call_to_action="What reliability practice would you add?",
        target_account="personal",
        tone="bold",
    )
    assert draft.platform.value == "linkedin"
    assert "• Verify outcomes" in draft.body
    assert "What reliability practice" in draft.body
    assert all(claim.provenance == Provenance.USER_PROVIDED for claim in draft.claims)


def test_local_linkedin_composer_rejects_unsupported_tone():
    with pytest.raises(ValueError, match="Tone"):
        ContentService().compose_linkedin_draft(
            uuid4(), "topic", "audience", ["point"], "", "personal", tone="hype"
        )
