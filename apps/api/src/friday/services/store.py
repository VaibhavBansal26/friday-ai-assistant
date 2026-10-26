from datetime import timedelta
from uuid import UUID

from friday.domain.models import (
    ActionRequest,
    AuditEvent,
    Approval,
    ApprovalStatus,
    Conversation,
    Message,
    MessageRole,
    Session,
    Task,
    TaskCreate,
    TaskUpdate,
    now_utc,
)

LOCAL_USER_ID = UUID("00000000-0000-4000-8000-000000000001")


class InMemoryStore:
    """Development adapter. Production uses repository interfaces backed by PostgreSQL."""

    def __init__(self) -> None:
        self.tasks: dict[UUID, Task] = {}
        self.actions: dict[UUID, ActionRequest] = {}
        self.approvals: dict[UUID, Approval] = {}
        self.sessions: dict[UUID, Session] = {}
        self.conversations: dict[UUID, Conversation] = {}
        self.messages: dict[UUID, list[Message]] = {}
        self.audit_events: list[AuditEvent] = []
        self.idempotency: dict[str, UUID] = {}

    def create_task(self, payload: TaskCreate) -> Task:
        task = Task(user_id=LOCAL_USER_ID, **payload.model_dump())
        self.tasks[task.id] = task
        return task

    def update_task(self, task_id: UUID, payload: TaskUpdate) -> Task:
        task = self.tasks[task_id]
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(task, key, value)
        task.updated_at = now_utc()
        return task

    def create_action(self, action: ActionRequest) -> Approval | None:
        existing = self.idempotency.get(action.idempotency_key)
        if existing is not None:
            if existing != action.id:
                raise ValueError("Idempotency key already belongs to another action")
            return next(
                (approval for approval in self.approvals.values() if approval.action_id == action.id),
                None,
            )
        self.actions[action.id] = action
        self.idempotency[action.idempotency_key] = action.id
        if action.risk >= 2:
            approval = Approval(action_id=action.id)
            self.approvals[approval.id] = approval
            return approval
        return None

    def append_audit(self, event: AuditEvent) -> AuditEvent:
        self.audit_events.append(event)
        return event

    def decide(self, approval_id: UUID, status: ApprovalStatus, user_id: UUID) -> Approval:
        approval = self.approvals[approval_id]
        approval.status = status
        approval.decided_by = user_id
        approval.decided_at = now_utc()
        return approval

    def create_session(self, user_id: UUID) -> Session:
        session = Session(user_id=user_id, expires_at=now_utc() + timedelta(hours=24))
        self.sessions[session.id] = session
        return session

    def create_conversation(self, user_id: UUID, title: str | None = None) -> Conversation:
        conversation = Conversation(user_id=user_id, title=title)
        self.conversations[conversation.id] = conversation
        self.messages[conversation.id] = []
        return conversation

    def add_message(self, conversation_id: UUID, role: MessageRole, content: str) -> Message:
        if conversation_id not in self.conversations:
            raise KeyError(conversation_id)
        message = Message(conversation_id=conversation_id, role=role, content=content)
        self.messages[conversation_id].append(message)
        conversation = self.conversations[conversation_id]
        conversation.updated_at = now_utc()
        return message


store = InMemoryStore()
