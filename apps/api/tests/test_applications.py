from uuid import uuid4

import pytest

from friday.domain.models import (
    ApplicationDraftCreate,
    ApplicationField,
    ApplicationFieldCategory,
    JobPosting,
    RiskLevel,
)
from friday.services.applications import ApplicationService


def job() -> JobPosting:
    return JobPosting(
        source="test",
        source_url="https://example.test/job",
        company="Acme",
        title="AI Engineer",
        description="Role",
        fingerprint="application-job",
        raw_payload={},
    )


def draft(fields, files=None) -> ApplicationDraftCreate:
    return ApplicationDraftCreate(
        job=job(),
        application_url="https://example.test/apply",
        resume_version_id=uuid4(),
        fields=fields,
        uploaded_files=files or [],
    )


def sourced_field(name="email"):
    return ApplicationField(
        name=name,
        label=name.title(),
        category=ApplicationFieldCategory.CONTACT,
        value="verified@example.test",
        source_fact_id=uuid4(),
        confidence="high",
        required=True,
    )


def test_factual_value_requires_verified_source():
    service = ApplicationService()
    field = sourced_field()
    field.source_fact_id = None
    with pytest.raises(ValueError, match="without a verified source"):
        service.create_draft(uuid4(), draft([field]))


def test_demographic_field_is_unanswered_by_default():
    service = ApplicationService()
    field = ApplicationField(
        name="gender",
        label="Gender",
        category=ApplicationFieldCategory.VOLUNTARY_DEMOGRAPHIC,
        value="Prefer not to say",
    )
    with pytest.raises(ValueError, match="remain unanswered"):
        service.create_draft(uuid4(), draft([field]))


def test_review_exposes_unanswered_and_low_confidence_fields():
    service = ApplicationService()
    user_id = uuid4()
    required = ApplicationField(
        name="authorization",
        label="Work authorization",
        category=ApplicationFieldCategory.WORK_AUTHORIZATION,
        required=True,
    )
    item = service.create_draft(user_id, draft([required, sourced_field()], ["resume.pdf"]))
    review = service.review(user_id, item.id)
    assert review.unanswered_fields == ["authorization"]
    assert not review.ready_for_approval


def test_ready_application_produces_level_three_action_not_submission():
    service = ApplicationService()
    user_id = uuid4()
    item = service.create_draft(user_id, draft([sourced_field()], ["resume.pdf"]))
    action = service.submission_action(user_id, item.id)
    assert action.risk == RiskLevel.HIGH_IMPACT
    assert action.action == "submit_application"
    assert service.drafts[item.id].status == "draft"


def test_blocked_review_cannot_request_submission_approval():
    service = ApplicationService()
    user_id = uuid4()
    required = ApplicationField(
        name="salary",
        label="Salary",
        category=ApplicationFieldCategory.SALARY,
        required=True,
    )
    item = service.create_draft(user_id, draft([required]))
    with pytest.raises(ValueError, match="unresolved blockers"):
        service.submission_action(user_id, item.id)
