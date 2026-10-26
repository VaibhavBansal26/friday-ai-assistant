import re
from uuid import UUID

from friday.domain.models import (
    ActionRequest,
    CalendarEvent,
    CalendarEventCreate,
    EmailReplyDraft,
    EmailSignal,
    EmailThread,
    RiskLevel,
)


class EmailService:
    def __init__(self) -> None:
        self.threads: dict[tuple[UUID, str], EmailThread] = {}
        self.drafts: dict[UUID, EmailReplyDraft] = {}

    def ingest_thread(self, thread: EmailThread) -> EmailThread:
        if not thread.messages:
            raise ValueError("Email thread must contain at least one message")
        self.threads[(thread.user_id, thread.id)] = thread
        return thread

    def signals(self, user_id: UUID, thread_id: str) -> list[EmailSignal]:
        thread = self.threads[(user_id, thread_id)]
        results: list[EmailSignal] = []
        patterns = {
            "interview_invitation": r"\b(interview|schedule a call|availability)\b",
            "assessment": r"\b(assessment|coding challenge|take-home)\b",
            "offer": r"\b(offer letter|pleased to offer)\b",
            "rejection": r"\b(not moving forward|other candidates)\b",
        }
        for message in thread.messages:
            text = f"{message.subject}\n{message.body}"
            for signal_type, pattern in patterns.items():
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    results.append(
                        EmailSignal(
                            signal_type=signal_type,
                            message_id=message.id,
                            evidence_excerpt=match.group(0),
                        )
                    )
        return results

    def create_reply_draft(self, user_id: UUID, thread_id: str, body: str) -> EmailReplyDraft:
        thread = self.threads[(user_id, thread_id)]
        if not body.strip():
            raise ValueError("Reply body cannot be empty")
        latest = thread.messages[-1]
        draft = EmailReplyDraft(
            user_id=user_id,
            thread_id=thread_id,
            recipients=[latest.sender],
            subject=(
                latest.subject
                if latest.subject.lower().startswith("re:")
                else f"Re: {latest.subject}"
            ),
            body=body,
            based_on_message_ids=[message.id for message in thread.messages],
        )
        self.drafts[draft.id] = draft
        return draft

    def send_action(self, user_id: UUID, draft_id: UUID) -> ActionRequest:
        draft = self.drafts[draft_id]
        if draft.user_id != user_id:
            raise PermissionError("Email draft belongs to another user")
        return ActionRequest(
            agent="email-reply-agent",
            action="send_email",
            target=", ".join(draft.recipients),
            risk=RiskLevel.EXTERNAL_COMMUNICATION,
            data_transmitted=["recipients", "subject", "body"],
            reversible=False,
            expected_outcome="Email provider accepts one message and returns a message ID",
            idempotency_key=f"email-send:{draft.id}",
            preview=draft.model_dump(mode="json"),
        )

    def create_new_draft(self, user_id: UUID, recipients: list[str], subject: str, body: str) -> EmailReplyDraft:
        if not recipients or not all("@" in item for item in recipients):
            raise ValueError("At least one valid recipient is required")
        if not subject.strip() or not body.strip():
            raise ValueError("Subject and body are required")
        draft = EmailReplyDraft(user_id=user_id, thread_id="", recipients=recipients, subject=subject.strip(), body=body.strip(), based_on_message_ids=[])
        self.drafts[draft.id] = draft
        return draft


class CalendarService:
    def __init__(self) -> None:
        self.events: dict[UUID, CalendarEvent] = {}

    def propose(self, user_id: UUID, payload: CalendarEventCreate) -> CalendarEvent:
        if payload.ends_at <= payload.starts_at:
            raise ValueError("Event end must be after start")
        event = CalendarEvent(user_id=user_id, **payload.model_dump())
        self.events[event.id] = event
        return event

    def conflicts(self, user_id: UUID, candidate: CalendarEvent) -> list[CalendarEvent]:
        return [
            event
            for event in self.events.values()
            if event.user_id == user_id
            and event.id != candidate.id
            and event.starts_at < candidate.ends_at
            and candidate.starts_at < event.ends_at
            and event.status != "cancelled"
        ]

    def create_action(self, user_id: UUID, event_id: UUID) -> ActionRequest:
        event = self.events[event_id]
        if event.user_id != user_id:
            raise PermissionError("Calendar event belongs to another user")
        if self.conflicts(user_id, event):
            raise ValueError("Proposed event conflicts with an existing event")
        return ActionRequest(
            agent="calendar-agent",
            action="create_calendar_event",
            target=event.title,
            risk=RiskLevel.EXTERNAL_COMMUNICATION,
            data_transmitted=["title", "start", "end", "attendees", "location"],
            reversible=True,
            expected_outcome="Calendar provider returns an event ID and confirmed time",
            idempotency_key=f"calendar-create:{event.id}",
            preview=event.model_dump(mode="json"),
        )
