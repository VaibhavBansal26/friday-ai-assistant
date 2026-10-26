import httpx
import pytest

from friday.domain.models import CandidateProfile, JobPosting
from datetime import UTC, datetime

from friday.services.jobs import GreenhouseAdapter, JobCatalog, JobMatchingService, MicrosoftCareersAlertParser


def job(**changes) -> JobPosting:
    values = {
        "source": "test",
        "source_url": "https://example.test/job",
        "company": "Acme",
        "title": "AI Engineer",
        "description": "Build agents",
        "required_skills": ["Python", "PyTorch"],
        "preferred_skills": ["LangGraph"],
        "location": "New York, NY",
        "remote_type": "onsite",
        "fingerprint": "test-fingerprint",
        "raw_payload": {},
    }
    values.update(changes)
    return JobPosting(**values)


@pytest.mark.asyncio
async def test_greenhouse_normalizes_without_inventing_publication_or_visa_data():
    async def handler(request: httpx.Request):
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 42,
                        "title": "AI Engineer",
                        "location": {"name": "Remote - US"},
                        "absolute_url": "https://example.test/jobs/42",
                        "content": "<p>Build reliable agents.</p>",
                        "updated_at": "2026-01-01T00:00:00Z",
                    }
                ]
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        jobs = await GreenhouseAdapter(client).fetch("acme", "Acme")
    job = jobs[0]
    assert job.description == "Build reliable agents."
    assert job.remote_type == "remote"
    assert job.published_at is None
    assert job.visa_information is None


@pytest.mark.asyncio
async def test_greenhouse_rejects_board_token_path_injection():
    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="Invalid"):
            await GreenhouseAdapter(client).fetch("../admin", "Acme")


def test_job_match_exposes_missing_required_skills_as_disqualifier():
    result = JobMatchingService().score(
        job(), CandidateProfile(verified_skill_ids={"Python"}, preferred_locations={"New York"})
    )
    assert result.missing_required_qualifications == ["pytorch"]
    assert any("missing required skills" in item for item in result.hard_disqualifiers)
    assert result.overall_score <= 49


def test_unknown_sponsorship_is_not_inferred_as_supported():
    result = JobMatchingService().score(
        job(),
        CandidateProfile(
            verified_skill_ids={"Python", "PyTorch"},
            preferred_locations={"New York"},
            requires_sponsorship=True,
        ),
    )
    assert result.work_authorization_score is None
    assert "sponsorship is unknown; the source does not provide this information" in result.risks


def test_explicit_no_sponsorship_is_hard_disqualifier():
    result = JobMatchingService().score(
        job(visa_information="No sponsorship is available"),
        CandidateProfile(
            verified_skill_ids={"Python", "PyTorch"},
            preferred_locations={"New York"},
            requires_sponsorship=True,
        ),
    )
    assert result.work_authorization_score == 0
    assert "source states that sponsorship is unavailable" in result.hard_disqualifiers


def test_unknown_salary_is_a_risk_not_an_invented_value():
    result = JobMatchingService().score(
        job(),
        CandidateProfile(
            verified_skill_ids={"Python", "PyTorch"}, minimum_salary=150000
        ),
    )
    assert "salary is not provided by the source" in result.risks


def test_job_catalog_deduplicates_by_fingerprint_and_preserves_first_seen():
    catalog = JobCatalog()
    first = job(required_skills=[])
    original_first_seen = first.first_seen_at
    second = job(required_skills=[])
    second.last_seen_at = second.last_seen_at.replace(microsecond=999999)
    catalog.ingest([first])
    catalog.ingest([second])
    stored = catalog.list_active()
    assert len(stored) == 1
    assert stored[0].first_seen_at == original_first_seen
    assert stored[0].last_seen_at == second.last_seen_at


MICROSOFT_ALERT = """
<b>We've found 19 new jobs that match your job search criteria</b>
<table><a href="https://microsoft.eightfold.ai/careerhub/explore/jobs/123?utm_source=alert&amp;domain=microsoft.com&amp;profile_type=candidate">Software Engineer II</a>
<div>United States, Washington, Redmond</div><span>Computer Science</span>
<span>Software Development</span><span>Strong Match</span></table>
<a href="https://microsoft.eightfold.ai/careerhub/explore/jobs?utm_source=alert">View all</a>
"""


def test_microsoft_alert_parser_preserves_links_and_message_evidence():
    postings, reported = MicrosoftCareersAlertParser().parse(
        body_html=MICROSOFT_ALERT, message_id="message-1",
        sender="Microsoft Careers <donotreply@email.careers.microsoft.com>",
        subject="19 new job(s) at Microsoft - Include eligible remote jobs",
        received_at=datetime(2026, 8, 20, 18, 54, tzinfo=UTC),
        message_url="https://mail.google.com/mail/#all/message-1",
    )
    assert reported == 19
    assert len(postings) == 1
    assert postings[0].external_id == "123"
    assert postings[0].alert_match == "Strong Match"
    assert postings[0].canonical_apply_url == "https://microsoft.eightfold.ai/careerhub/explore/jobs/123?domain=microsoft.com&profile_type=candidate"
    assert postings[0].evidence["gmail_url"].endswith("message-1")


def test_alert_ingestion_is_idempotent_and_never_reports_applications():
    posting = job(alert_match="Strong Match", evidence={"gmail_url": "https://mail.test/1"})
    catalog = JobCatalog()
    first = catalog.ingest_alert([posting], 19, "https://mail.test/1")
    second = catalog.ingest_alert([posting], 19, "https://mail.test/1")
    assert (first.created_count, first.deduplicated_count) == (1, 0)
    assert (second.created_count, second.deduplicated_count) == (0, 1)
    assert second.applications_submitted == 0
