import hashlib
import html
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

import httpx

from friday.domain.models import CandidateProfile, JobAlertIngestionResult, JobMatch, JobPosting, now_utc


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(text).split())


def _canonical_job_url(value: str) -> str:
    """Keep the source link usable while dropping alert tracking parameters."""
    parts = urlsplit(html.unescape(value))
    if parts.scheme != "https" or parts.hostname != "microsoft.eightfold.ai":
        raise ValueError("Microsoft alert contained an unexpected job URL")
    kept = [(key, item) for key, values in parse_qs(parts.query).items()
            if key in {"domain", "profile_type"} for item in values]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept), ""))


class _MicrosoftAlertHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.capture: str | None = None
        self.buffer: list[str] = []
        self.reported_count = 0

    def _finish_card(self) -> None:
        if self.current and self.current.get("title"):
            self.cards.append(self.current)
        self.current, self.capture, self.buffer = None, None, []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and "/careerhub/explore/jobs/" in (values.get("href") or ""):
            self._finish_card()
            self.current = {"url": values["href"], "tags": []}
            self.capture, self.buffer = "title", []
        elif tag == "a" and self.current and self.current.get("match"):
            self._finish_card()
        elif self.current and tag in {"div", "span"}:
            self.capture, self.buffer = "text", []

    def handle_data(self, data: str) -> None:
        match = re.search(r"found\s+(\d+)\s+new jobs", data, re.I)
        if match:
            self.reported_count = int(match.group(1))
        if self.current and self.capture:
            self.buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self.current:
            return
        text = " ".join("".join(self.buffer).split())
        if tag == "a" and self.capture == "title":
            self.current["title"] = text
            self.capture, self.buffer = None, []
        elif tag in {"div", "span"} and self.capture == "text":
            if text:
                if re.fullmatch(r"(?:Strong|Good|Potential) Match", text, re.I):
                    self.current["match"] = text
                elif text not in self.current["tags"]:
                    self.current["tags"].append(text)
            self.capture, self.buffer = None, []

    def close(self) -> None:
        super().close()
        self._finish_card()


class MicrosoftCareersAlertParser:
    """Parse only job cards evidenced in a Microsoft Careers notification."""

    def parse(self, *, body_html: str, message_id: str, sender: str, subject: str,
              received_at: datetime, message_url: str) -> tuple[list[JobPosting], int]:
        parser = _MicrosoftAlertHTMLParser()
        parser.feed(body_html)
        timestamp = now_utc()
        postings: list[JobPosting] = []
        for card in parser.cards:
            source_url = html.unescape(card["url"])
            canonical_url = _canonical_job_url(source_url)
            external_id = urlsplit(canonical_url).path.rstrip("/").split("/")[-1]
            tags = [item for item in card["tags"] if item != card.get("match")]
            location = next((item for item in tags if item.startswith("United States")), None)
            skills = [item for item in tags if item != location]
            fingerprint = hashlib.sha256(f"microsoft|{external_id}".encode()).hexdigest()
            excerpt = " · ".join(filter(None, [card["title"], location, *skills, card.get("match")]))
            postings.append(JobPosting(
                external_id=external_id, source="gmail_microsoft_careers", source_url=source_url,
                canonical_apply_url=canonical_url, company="Microsoft", title=card["title"],
                description="Job surfaced by a Microsoft Careers saved-search email.",
                preferred_skills=skills, location=location,
                remote_type="remote_eligible" if "remote" in subject.casefold() else "unknown",
                first_seen_at=timestamp, last_seen_at=timestamp, fingerprint=fingerprint,
                alert_match=card.get("match"),
                evidence={"gmail_message_id": message_id, "gmail_url": message_url,
                          "sender": sender, "subject": subject,
                          "received_at": received_at.isoformat(), "source_excerpt": excerpt},
                raw_payload={"alert_tags": skills, "alert_match": card.get("match"),
                             "reported_alert_count": parser.reported_count},
            ))
        return postings, parser.reported_count


class GreenhouseAdapter:
    """Read-only direct ATS adapter using Greenhouse's public job-board endpoint."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def fetch(self, board_token: str, company: str) -> list[JobPosting]:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", board_token):
            raise ValueError("Invalid Greenhouse board token")
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        response = await self.client.get(url, timeout=20)
        response.raise_for_status()
        payload = response.json()
        return [self._normalize(item, company, url) for item in payload.get("jobs", [])]

    def _normalize(self, item: dict[str, Any], company: str, source_url: str) -> JobPosting:
        description = strip_html(item.get("content") or "")
        location = (item.get("location") or {}).get("name")
        external_id = str(item["id"]) if item.get("id") is not None else None
        canonical_url = item.get("absolute_url")
        fingerprint_input = "|".join(
            [company.casefold(), str(item.get("title", "")).casefold(), str(location).casefold()]
        )
        timestamp = now_utc()
        return JobPosting(
            external_id=external_id,
            source="greenhouse",
            source_url=source_url,
            canonical_apply_url=canonical_url,
            company=company,
            title=item.get("title") or "Unknown title",
            description=description,
            location=location,
            remote_type=self._remote_type(location),
            published_at=None,
            first_seen_at=timestamp,
            last_seen_at=timestamp,
            fingerprint=hashlib.sha256(fingerprint_input.encode()).hexdigest(),
            raw_payload=item,
        )

    @staticmethod
    def _remote_type(location: str | None) -> str:
        if not location:
            return "unknown"
        lowered = location.casefold()
        if "remote" in lowered:
            return "remote"
        if "hybrid" in lowered:
            return "hybrid"
        return "onsite"


class JobMatchingService:
    def score(self, job: JobPosting, candidate: CandidateProfile) -> JobMatch:
        required = {skill.casefold() for skill in job.required_skills}
        preferred = {skill.casefold() for skill in job.preferred_skills}
        verified = {skill.casefold() for skill in candidate.verified_skill_ids}
        missing_required = sorted(required - verified)
        missing_preferred = sorted(preferred - verified)
        required_score = 100 if not required else round(100 * len(required & verified) / len(required))

        location_score = self._location_score(job, candidate)
        hard_disqualifiers: list[str] = []
        risks: list[str] = []
        authorization_score: int | None = None

        if candidate.minimum_salary is not None and job.salary_max is not None:
            if job.salary_max < candidate.minimum_salary:
                hard_disqualifiers.append("maximum salary is below the candidate minimum")
        elif candidate.minimum_salary is not None:
            risks.append("salary is not provided by the source")

        if candidate.requires_sponsorship is True:
            if job.visa_information is None:
                risks.append("sponsorship is unknown; the source does not provide this information")
            elif "no sponsorship" in job.visa_information.casefold():
                hard_disqualifiers.append("source states that sponsorship is unavailable")
                authorization_score = 0
            else:
                risks.append("visa text requires human confirmation")
        elif candidate.requires_sponsorship is False:
            authorization_score = 100
        else:
            risks.append("candidate work-authorization requirements are unknown")

        if missing_required:
            hard_disqualifiers.append("missing required skills: " + ", ".join(missing_required))
        if location_score == 0:
            hard_disqualifiers.append("location does not match verified preferences")

        components = [required_score, location_score]
        if authorization_score is not None:
            components.append(authorization_score)
        overall = round(sum(components) / len(components))
        if hard_disqualifiers:
            overall = min(overall, 49)

        return JobMatch(
            job_id=job.id,
            overall_score=overall,
            required_skill_score=required_score,
            location_score=location_score,
            work_authorization_score=authorization_score,
            missing_required_qualifications=missing_required,
            missing_preferred_qualifications=missing_preferred,
            hard_disqualifiers=hard_disqualifiers,
            risks=risks,
        )

    @staticmethod
    def _location_score(job: JobPosting, candidate: CandidateProfile) -> int:
        if candidate.remote_preference == "remote" and job.remote_type == "remote":
            return 100
        if not candidate.preferred_locations:
            return 50
        if job.location is None:
            return 25
        location = job.location.casefold()
        return 100 if any(place.casefold() in location for place in candidate.preferred_locations) else 0


class JobCatalog:
    def __init__(self) -> None:
        self.jobs: dict[str, JobPosting] = {}

    def ingest(self, postings: list[JobPosting]) -> list[JobPosting]:
        for posting in postings:
            existing = self.jobs.get(posting.fingerprint)
            if existing:
                existing.last_seen_at = posting.last_seen_at
                existing.active = posting.active
                existing.raw_payload = posting.raw_payload
                existing.source_url = posting.source_url
                existing.canonical_apply_url = posting.canonical_apply_url
                existing.alert_match = posting.alert_match
                existing.evidence = posting.evidence
            else:
                self.jobs[posting.fingerprint] = posting
        return postings

    def ingest_alert(self, postings: list[JobPosting], reported_count: int,
                     source_message_url: str) -> JobAlertIngestionResult:
        before = set(self.jobs)
        self.ingest(postings)
        created = sum(item.fingerprint not in before for item in postings)
        rank = {"strong match": 0, "good match": 1, "potential match": 2}
        shortlist = sorted(postings, key=lambda item: (rank.get((item.alert_match or "").casefold(), 9), item.title))
        return JobAlertIngestionResult(
            source="gmail_microsoft_careers", source_message_url=source_message_url,
            reported_count=reported_count, parsed_count=len(postings), created_count=created,
            deduplicated_count=len(postings) - created, shortlist=shortlist,
        )

    def list_active(self) -> list[JobPosting]:
        return sorted(
            (job for job in self.jobs.values() if job.active),
            key=lambda job: job.first_seen_at,
            reverse=True,
        )
