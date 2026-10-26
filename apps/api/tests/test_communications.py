from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from friday.domain.models import (
    CalendarEventCreate,
    EmailMessage,
    EmailThread,
    RiskLevel,
)
from friday.services.communications import CalendarService, EmailService


def thread(user_id):
    return EmailThread(
        id="thread-1",
        user_id=user_id,
        messages=[
            EmailMessage(
                id="message-1",
                sender="recruiter@example.test",
                recipients=["user@example.test"],
                subject="Interview availability",
                body="Please share your availability for an interview.",
                received_at=datetime.now(UTC),
            )
        ],
    )


def test_email_draft_requires_thread_context_and_records_sources():
    service = EmailService()
    user_id = uuid4()
    service.ingest_thread(thread(user_id))
    draft = service.create_reply_draft(user_id, "thread-1", "I am available Tuesday.")
    assert draft.based_on_message_ids == ["message-1"]
    assert draft.recipients == ["recruiter@example.test"]


def test_email_signal_contains_evidence_not_invented_deadline():
    service = EmailService()
    user_id = uuid4()
    service.ingest_thread(thread(user_id))
    signal = service.signals(user_id, "thread-1")[0]
    assert signal.signal_type == "interview_invitation"
    assert signal.evidence_excerpt.lower() == "interview"
    assert signal.deadline is None


def test_email_send_is_level_two_preview_only():
    service = EmailService()
    user_id = uuid4()
    service.ingest_thread(thread(user_id))
    draft = service.create_reply_draft(user_id, "thread-1", "Thank you.")
    action = service.send_action(user_id, draft.id)
    assert action.risk == RiskLevel.EXTERNAL_COMMUNICATION
    assert action.action == "send_email"
    assert draft.id in service.drafts


def test_calendar_rejects_invalid_time_range():
    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="after start"):
        CalendarService().propose(
            uuid4(), CalendarEventCreate(title="Invalid", starts_at=now, ends_at=now)
        )


def test_calendar_conflict_blocks_creation_preview():
    service = CalendarService()
    user_id = uuid4()
    start = datetime.now(UTC) + timedelta(days=1)
    service.propose(
        user_id,
        CalendarEventCreate(title="Existing", starts_at=start, ends_at=start + timedelta(hours=1)),
    )
    candidate = service.propose(
        user_id,
        CalendarEventCreate(
            title="Interview",
            starts_at=start + timedelta(minutes=30),
            ends_at=start + timedelta(hours=2),
        ),
    )
    with pytest.raises(ValueError, match="conflicts"):
        service.create_action(user_id, candidate.id)


def test_clear_calendar_event_creates_level_two_action():
    service = CalendarService()
    user_id = uuid4()
    start = datetime.now(UTC) + timedelta(days=2)
    event = service.propose(
        user_id,
        CalendarEventCreate(title="Interview", starts_at=start, ends_at=start + timedelta(hours=1)),
    )
    action = service.create_action(user_id, event.id)
    assert action.risk == RiskLevel.EXTERNAL_COMMUNICATION
    assert event.status == "proposed"
