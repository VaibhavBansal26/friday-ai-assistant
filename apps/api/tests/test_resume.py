from uuid import uuid4

import pytest

from friday.domain.models import (
    JobPosting,
    Provenance,
    ResumeClaimCreate,
    ResumeTailoringRequest,
    VerifiedFact,
)
from friday.services.resume import ResumeService


def fact(user_id, value: str) -> VerifiedFact:
    return VerifiedFact(
        user_id=user_id,
        namespace="resume",
        fact_key="project",
        value=value,
        provenance=Provenance.USER_PROVIDED,
        source_id="master-resume",
    )


def job(required_skills: list[str]) -> JobPosting:
    return JobPosting(
        source="test",
        source_url="https://example.test/job",
        company="Acme",
        title="AI Engineer",
        description="Role",
        required_skills=required_skills,
        fingerprint="resume-test-job",
        raw_payload={},
    )


def registered(service: ResumeService, user_id, value="Built Python services for agents"):
    source = fact(user_id, value)
    claim = service.register_claim(
        user_id,
        ResumeClaimCreate(
            claim_text=value,
            verified_fact_id=source.id,
            skills={"Python"},
            source_excerpt=value,
        ),
        {source.id: source},
    )
    return claim


def test_resume_claim_requires_owned_verified_fact():
    service = ResumeService()
    with pytest.raises(ValueError, match="owned verified fact"):
        service.register_claim(
            uuid4(),
            ResumeClaimCreate(
                claim_text="Built systems",
                verified_fact_id=uuid4(),
                source_excerpt="Built systems",
            ),
            {},
        )


def test_tailored_claim_keeps_fact_traceability():
    service = ResumeService()
    user_id = uuid4()
    claim = registered(service, user_id)
    result = service.tailor(
        user_id, ResumeTailoringRequest(job=job(["Python"]), claim_ids=[claim.id])
    )
    assert result.selected_claims[0].verified_fact_id == claim.verified_fact_id
    assert result.selected_claims[0].source_claim_id == claim.id


def test_rewrite_cannot_invent_metric():
    service = ResumeService()
    user_id = uuid4()
    claim = registered(service, user_id)
    with pytest.raises(ValueError, match="unsupported metrics"):
        service.tailor(
            user_id,
            ResumeTailoringRequest(
                job=job(["Python"]),
                claim_ids=[claim.id],
                proposed_rewrites={claim.id: "Improved Python performance by 40%"},
            ),
        )


def test_rewrite_cannot_add_unsupported_required_technology():
    service = ResumeService()
    user_id = uuid4()
    claim = registered(service, user_id)
    with pytest.raises(ValueError, match="unsupported technologies"):
        service.tailor(
            user_id,
            ResumeTailoringRequest(
                job=job(["Python", "PyTorch"]),
                claim_ids=[claim.id],
                proposed_rewrites={claim.id: "Built Python and PyTorch services"},
            ),
        )


def test_missing_skill_is_reported_not_added():
    service = ResumeService()
    user_id = uuid4()
    claim = registered(service, user_id)
    result = service.tailor(
        user_id,
        ResumeTailoringRequest(job=job(["Python", "PyTorch"]), claim_ids=[claim.id]),
    )
    assert result.missing_required_skills == ["pytorch"]
    assert "pytorch" in result.warnings[0]
