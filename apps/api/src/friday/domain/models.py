from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import IntEnum, StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def now_utc() -> datetime:
    return datetime.now(UTC)


class Provenance(StrEnum):
    VERIFIED = "verified_fact"
    RETRIEVED = "retrieved_fact"
    USER_PROVIDED = "user_provided_fact"
    INFERENCE = "inference"
    RECOMMENDATION = "recommendation"
    UNKNOWN = "unknown"


class RiskLevel(IntEnum):
    READ_ONLY = 0
    LOCAL_REVERSIBLE = 1
    EXTERNAL_COMMUNICATION = 2
    HIGH_IMPACT = 3
    DESTRUCTIVE_OR_FINANCIAL = 4


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED_ONCE = "approved_once"
    APPROVED_SESSION = "approved_session"
    REJECTED = "rejected"
    EXPIRED = "expired"


class ExecutionStatus(StrEnum):
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_for_approval"
    ACTING = "acting"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class Claim(BaseModel):
    text: str
    provenance: Provenance
    source_id: str | None = None
    source_excerpt: str | None = None
    verified_at: datetime | None = None


class ActionRequest(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    agent: str
    action: str
    target: str
    risk: RiskLevel
    data_transmitted: list[str] = Field(default_factory=list)
    reversible: bool
    expected_outcome: str
    idempotency_key: str
    preview: dict[str, Any] = Field(default_factory=dict)


class Approval(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    status: ApprovalStatus = ApprovalStatus.PENDING
    scope: str = "once"
    decided_by: UUID | None = None
    decided_at: datetime | None = None


class ToolEvidence(BaseModel):
    tool_run_id: UUID = Field(default_factory=uuid4)
    action_id: UUID
    provider: str
    success: bool
    status_code: int | None = None
    result_id: str | None = None
    result_url: str | None = None
    resulting_state: str | None = None
    error_code: str | None = None
    observed_at: datetime = Field(default_factory=now_utc)


class VerificationResult(BaseModel):
    verified: bool
    outcome: str
    evidence_ids: list[UUID] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)


class TaskStatus(StrEnum):
    INBOX = "inbox"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING = "waiting"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    priority: TaskPriority = TaskPriority.MEDIUM
    category: str = "general"
    completion_criteria: list[str] = Field(default_factory=list)


class Task(TaskCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID = UUID("00000000-0000-4000-8000-000000000001")
    status: TaskStatus = TaskStatus.INBOX
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    category: str | None = None
    completion_criteria: list[str] | None = None


class Session(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    created_at: datetime = Field(default_factory=now_utc)
    expires_at: datetime


class SessionGrant(BaseModel):
    session: Session
    token: str = Field(repr=False)


class Conversation(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM_EVENT = "system_event"


class Message(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID
    role: MessageRole
    content: str = Field(min_length=1, max_length=50_000)
    claims: list[Claim] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class ModelCapability(StrEnum):
    TEXT = "text"
    VISION = "vision"
    AUDIO = "audio"
    TOOLS = "tools"
    STRUCTURED_OUTPUT = "structured_output"


class PrivacyClass(StrEnum):
    STANDARD = "standard"
    SENSITIVE = "sensitive"
    LOCAL_ONLY = "local_only"


class ModelRouteRequest(BaseModel):
    task_type: str
    capabilities: set[ModelCapability] = Field(default_factory=lambda: {ModelCapability.TEXT})
    privacy: PrivacyClass = PrivacyClass.STANDARD
    maximum_latency_ms: int | None = Field(default=None, gt=0)
    maximum_cost_usd: float | None = Field(default=None, ge=0)
    reasoning_depth: str = "standard"


class ModelRoute(BaseModel):
    provider: str
    model: str
    fallback_models: list[str] = Field(default_factory=list)
    reason_codes: list[str]
    timeout_ms: int
    live: bool = True


class AuditEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID | None = None
    session_id: UUID | None = None
    event_type: str
    actor: str
    target_type: str | None = None
    target_id: str | None = None
    safe_payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class EventEnvelope(BaseModel):
    version: str = "1"
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    session_id: UUID
    sequence: int = Field(ge=0)
    correlation_id: UUID
    timestamp: datetime = Field(default_factory=now_utc)
    payload: dict[str, Any] = Field(default_factory=dict)


class VoiceTranscriptAssessment(BaseModel):
    transcript: str
    normalized_transcript: str
    risk: RiskLevel
    ambiguous: bool
    ambiguity_reasons: list[str] = Field(default_factory=list)
    requires_readback: bool
    readback: str | None = None


class RealtimeSessionDescriptor(BaseModel):
    session_id: str
    provider: str
    model: str
    client_secret: str = Field(repr=False)
    expires_at: datetime
    transport: str = "webrtc"


class CredentialStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class CredentialMetadata(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    provider: str
    account_label: str
    scopes: set[str] = Field(default_factory=set)
    status: CredentialStatus = CredentialStatus.ACTIVE
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=now_utc)
    last_accessed_at: datetime | None = None


class CredentialCapability(BaseModel):
    credential_id: UUID
    provider: str
    allowed_scopes: set[str]
    expires_at: datetime
    task_id: UUID


class OAuthGrantMetadata(BaseModel):
    credential_id: UUID
    provider: str
    scopes: set[str]
    access_expires_at: datetime
    refresh_rotated_at: datetime | None = None
    status: CredentialStatus = CredentialStatus.ACTIVE


class NotificationSeverity(StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


class Notification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str = Field(max_length=120)
    body: str = Field(max_length=300)
    severity: NotificationSeverity = NotificationSeverity.INFO
    category: str
    target_path: str | None = None
    deduplication_key: str
    read: bool = False
    dismissed: bool = False
    created_at: datetime = Field(default_factory=now_utc)


class NotificationCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=300)
    severity: NotificationSeverity = NotificationSeverity.INFO
    category: str = "general"
    target_path: str | None = None
    deduplication_key: str = Field(min_length=1, max_length=200)


class PrivacyPreference(StrEnum):
    STANDARD = "standard"
    SENSITIVE_LOCAL_PREFERRED = "sensitive_local_preferred"
    LOCAL_ONLY = "local_only"


class UserSettings(BaseModel):
    user_id: UUID
    privacy_preference: PrivacyPreference = PrivacyPreference.STANDARD
    notifications_enabled: bool = False
    voice_enabled: bool = True
    voice_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    reduced_motion: bool = False
    default_model_route: str = Field(default="provider-default", max_length=100)
    external_writes_enabled: bool = False
    memory_writes_require_approval: bool = True
    updated_at: datetime = Field(default_factory=now_utc)


class UserSettingsUpdate(BaseModel):
    privacy_preference: PrivacyPreference | None = None
    notifications_enabled: bool | None = None
    voice_enabled: bool | None = None
    voice_speed: float | None = Field(default=None, ge=0.5, le=2.0)
    reduced_motion: bool | None = None
    default_model_route: str | None = Field(default=None, min_length=1, max_length=100)
    memory_writes_require_approval: bool | None = None


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    goal: str | None = Field(default=None, max_length=2000)


class Project(ProjectCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: ProjectStatus = ProjectStatus.ACTIVE
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class IdeaCreate(BaseModel):
    problem: str = Field(min_length=1, max_length=3000)
    target_user: str | None = Field(default=None, max_length=1000)
    proposed_solution: str | None = Field(default=None, max_length=3000)


class Idea(IdeaCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    decision_log: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class VerifiedFactCreate(BaseModel):
    namespace: str = Field(min_length=1, max_length=100)
    fact_key: str = Field(min_length=1, max_length=160)
    value: Any
    provenance: Provenance
    source_id: str | None = None
    source_excerpt: str | None = None


class VerifiedFact(VerifiedFactCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    verified_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime = Field(default_factory=now_utc)


class MemorySensitivity(StrEnum):
    LOW = "low"
    PERSONAL = "personal"
    SENSITIVE = "sensitive"


class MemoryStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class MemoryProposalCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    source_id: str = Field(min_length=1, max_length=300)
    sensitivity: MemorySensitivity = MemorySensitivity.PERSONAL
    confidence: str = "unknown"
    expires_at: datetime | None = None


class MemoryProposal(MemoryProposalCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: MemoryStatus = MemoryStatus.PROPOSED
    contradiction_ids: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=now_utc)


class SearchCitation(BaseModel):
    collection: str
    path: str
    doc_id: str | None = None
    title: str | None = None
    snippet: str
    score: float | None = None


class KnowledgeSearchResult(BaseModel):
    query: str
    citations: list[SearchCitation]
    answerable: bool


class JobPosting(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    external_id: str | None = None
    source: str
    source_url: str
    canonical_apply_url: str | None = None
    company: str
    title: str
    description: str
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    location: str | None = None
    remote_type: str = "unknown"
    employment_type: str | None = None
    seniority: str | None = None
    salary_min: Decimal | None = None
    salary_max: Decimal | None = None
    salary_currency: str | None = None
    visa_information: str | None = None
    published_at: datetime | None = None
    first_seen_at: datetime = Field(default_factory=now_utc)
    last_seen_at: datetime = Field(default_factory=now_utc)
    active: bool = True
    fingerprint: str
    raw_payload: dict[str, Any]
    alert_match: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class JobAlertIngestionResult(BaseModel):
    source: str
    source_message_url: str
    reported_count: int
    parsed_count: int
    created_count: int
    deduplicated_count: int
    shortlist: list[JobPosting]
    applications_submitted: int = 0


class CandidateProfile(BaseModel):
    verified_skill_ids: set[str] = Field(default_factory=set)
    preferred_locations: set[str] = Field(default_factory=set)
    remote_preference: str | None = None
    minimum_salary: Decimal | None = None
    work_authorization: str | None = None
    requires_sponsorship: bool | None = None


class JobMatch(BaseModel):
    job_id: UUID
    overall_score: int = Field(ge=0, le=100)
    required_skill_score: int = Field(ge=0, le=100)
    experience_score: int | None = Field(default=None, ge=0, le=100)
    project_relevance_score: int | None = Field(default=None, ge=0, le=100)
    location_score: int = Field(ge=0, le=100)
    work_authorization_score: int | None = Field(default=None, ge=0, le=100)
    missing_required_qualifications: list[str] = Field(default_factory=list)
    missing_preferred_qualifications: list[str] = Field(default_factory=list)
    hard_disqualifiers: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_resume_version_id: UUID | None = None


class ResumeClaimCreate(BaseModel):
    claim_text: str = Field(min_length=1, max_length=2000)
    verified_fact_id: UUID
    skills: set[str] = Field(default_factory=set)
    source_excerpt: str = Field(min_length=1, max_length=3000)


class ResumeClaim(ResumeClaimCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    created_at: datetime = Field(default_factory=now_utc)


class TailoredResumeClaim(BaseModel):
    source_claim_id: UUID
    verified_fact_id: UUID
    original_text: str
    tailored_text: str
    matched_skills: list[str] = Field(default_factory=list)
    transformation_note: str


class ResumeTailoringRequest(BaseModel):
    job: JobPosting
    claim_ids: list[UUID]
    proposed_rewrites: dict[UUID, str] = Field(default_factory=dict)


class ResumeTailoringResult(BaseModel):
    job_id: UUID
    selected_claims: list[TailoredResumeClaim]
    omitted_claim_ids: list[UUID]
    missing_required_skills: list[str]
    warnings: list[str] = Field(default_factory=list)


class ApplicationFieldCategory(StrEnum):
    CONTACT = "contact"
    WORK_AUTHORIZATION = "work_authorization"
    SALARY = "salary"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    VOLUNTARY_DEMOGRAPHIC = "voluntary_demographic"
    OTHER = "other"


class ApplicationField(BaseModel):
    name: str
    label: str
    category: ApplicationFieldCategory
    value: Any = None
    source_fact_id: UUID | None = None
    confidence: str = "unknown"
    required: bool = False


class ApplicationDraftCreate(BaseModel):
    job: JobPosting
    application_url: str
    resume_version_id: UUID
    cover_letter: str | None = None
    fields: list[ApplicationField]
    uploaded_files: list[str] = Field(default_factory=list)


class ApplicationDraft(ApplicationDraftCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: str = "draft"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ApplicationReview(BaseModel):
    application_id: UUID
    company: str
    role: str
    application_url: str
    resume_version_id: UUID
    fields: list[ApplicationField]
    uploaded_files: list[str]
    unanswered_fields: list[str]
    low_confidence_fields: list[str]
    voluntary_demographic_fields: list[str]
    ready_for_approval: bool
    blockers: list[str]


class EmailMessage(BaseModel):
    id: str
    sender: str
    recipients: list[str]
    subject: str
    body: str
    received_at: datetime


class EmailThread(BaseModel):
    id: str
    user_id: UUID
    messages: list[EmailMessage]


class EmailSignal(BaseModel):
    signal_type: str
    message_id: str
    evidence_excerpt: str
    deadline: datetime | None = None


class EmailReplyDraft(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    thread_id: str
    recipients: list[str]
    subject: str
    body: str
    based_on_message_ids: list[str]
    created_at: datetime = Field(default_factory=now_utc)


class CalendarEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    title: str
    starts_at: datetime
    ends_at: datetime
    attendees: list[str] = Field(default_factory=list)
    location: str | None = None
    status: str = "proposed"
    source_reference: str | None = None


class CalendarEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: datetime
    ends_at: datetime
    attendees: list[str] = Field(default_factory=list)
    location: str | None = None
    source_reference: str | None = None


class CommandRisk(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    DESTRUCTIVE = "destructive"
    EXTERNAL_WRITE = "external_write"


class RepositoryContext(BaseModel):
    root: str
    branch: str | None = None
    dirty: bool
    changed_files: list[str] = Field(default_factory=list)
    instruction_files: list[str] = Field(default_factory=list)


class CommandAssessment(BaseModel):
    command: list[str]
    risk: CommandRisk
    allowed: bool
    requires_approval: bool
    reason: str


class CommandEvidence(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    started_at: datetime
    finished_at: datetime
    verified_success: bool


class BrowserActionType(StrEnum):
    NAVIGATE = "navigate"
    READ = "read"
    FILL = "fill"
    UPLOAD = "upload"
    SUBMIT = "submit"


class BrowserAction(BaseModel):
    action_type: BrowserActionType
    url: str
    target: str | None = None
    data_fields: list[str] = Field(default_factory=list)
    idempotency_key: str | None = None


class BrowserActionAssessment(BaseModel):
    allowed: bool
    requires_approval: bool
    requires_manual_intervention: bool = False
    reason: str


class BrowserCompletionEvidence(BaseModel):
    action_type: BrowserActionType
    confirmation_url: str | None = None
    confirmation_number: str | None = None
    provider_state: str | None = None
    screenshot_id: str | None = None
    clicked_submit: bool = False


class ConceptStatus(StrEnum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    MASTERED = "mastered"


class LearningConcept(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    status: ConceptStatus = ConceptStatus.NEW
    confidence: str = "unknown"
    accuracy: float | None = Field(default=None, ge=0, le=1)
    last_reviewed_at: datetime | None = None
    next_review_at: datetime | None = None
    common_mistakes: list[str] = Field(default_factory=list)


class StudySessionCreate(BaseModel):
    concept_ids: list[UUID]
    objective: str = Field(min_length=1, max_length=500)
    exercise: str = Field(min_length=1, max_length=2000)
    completion_criteria: list[str] = Field(min_length=1)


class StudySession(StudySessionCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: str = "planned"
    score: float | None = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=now_utc)
    completed_at: datetime | None = None


class InterviewAnswerEvaluation(BaseModel):
    correctness: int = Field(ge=1, le=5)
    technical_depth: int = Field(ge=1, le=5)
    structure: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    relevance: int = Field(ge=1, le=5)
    tradeoff_awareness: int = Field(ge=1, le=5)
    ownership: int = Field(ge=1, le=5)
    evidence_use: int = Field(ge=1, le=5)
    followup_handling: int = Field(ge=1, le=5)
    strengths: list[str] = Field(default_factory=list)
    missing_details: list[str] = Field(default_factory=list)
    incorrect_statements: list[str] = Field(default_factory=list)
    likely_followups: list[str] = Field(default_factory=list)
    topics_to_review: list[str] = Field(default_factory=list)


class WorkflowStatus(StrEnum):
    PENDING = "pending"
    WAITING_APPROVAL = "waiting_approval"
    RUNNING = "running"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"
    CANCELLED = "cancelled"


class RetryClass(StrEnum):
    SAFE = "safe"
    CONDITIONAL = "conditional"
    IRREVERSIBLE = "irreversible"


class WorkflowRun(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    workflow_type: str
    idempotency_key: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    retry_class: RetryClass
    maximum_attempts: int = Field(ge=1, le=10)
    attempt_count: int = 0
    timeout_seconds: int = Field(gt=0)
    approval_id: UUID | None = None
    compensation_action: str | None = None
    verification_state: str = "pending"
    failure_reason: str | None = None
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class ReviewSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PullRequestFinding(BaseModel):
    severity: ReviewSeverity
    confidence: str
    file: str
    line: int | None = Field(default=None, ge=1)
    region: str | None = None
    problem: str
    why_it_matters: str
    failure_scenario: str
    suggested_fix: str


class GitOperationEvidence(BaseModel):
    operation: str
    local_commit: str | None = None
    remote_commit: str | None = None
    pull_request_number: int | None = None
    pull_request_url: str | None = None
    provider_comment_id: str | None = None
    provider_state: str | None = None


class WebsitePage(BaseModel):
    path: str
    title: str
    purpose: str


class WebsiteProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    audience: str = Field(min_length=1, max_length=1000)
    goal: str = Field(min_length=1, max_length=2000)
    pages: list[WebsitePage] = Field(min_length=1)
    stack: list[str] = Field(default_factory=lambda: ["Next.js", "React", "TypeScript"])


class WebsiteProject(WebsiteProjectCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: str = "planned"
    created_at: datetime = Field(default_factory=now_utc)


class WebsiteQaEvidence(BaseModel):
    project_id: UUID
    preview_url: str | None = None
    tested_viewports: list[str] = Field(default_factory=list)
    screenshot_ids: list[str] = Field(default_factory=list)
    accessibility_violations: list[str] = Field(default_factory=list)
    broken_links: list[str] = Field(default_factory=list)
    console_errors: list[str] = Field(default_factory=list)
    test_exit_code: int | None = None
    build_exit_code: int | None = None


class TraceEvent(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID
    event_type: str
    agent: str | None = None
    tool: str | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    token_usage: dict[str, int] = Field(default_factory=dict)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    approval_status: str | None = None
    verification_status: str | None = None
    safe_attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=now_utc)


class EvaluationResult(BaseModel):
    metric: str
    passed: bool
    observed: float
    required: float
    sample_size: int
    notes: str | None = None


class ReleaseGateResult(BaseModel):
    releasable: bool
    results: list[EvaluationResult]
    blockers: list[str]


class RelationshipAuthority(StrEnum):
    SOURCE_VERIFIED = "source_verified"
    GRAPH_DERIVED = "graph_derived"
    MEMORY_INFERRED = "memory_inferred"


class RelationshipProposal(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    subject: str
    predicate: str
    object: str
    authority: RelationshipAuthority
    source_ids: list[str] = Field(default_factory=list)
    confidence: str = "unknown"
    status: str = "shadow"
    created_at: datetime = Field(default_factory=now_utc)


class RepositoryGraphEdge(BaseModel):
    source_path: str
    target_path: str
    relationship: str
    source_hash: str | None = None
    target_hash: str | None = None
    authority: RelationshipAuthority = RelationshipAuthority.GRAPH_DERIVED


class GraphImpactSuggestion(BaseModel):
    changed_path: str
    related_paths: list[str]
    verified_paths: list[str]
    unverified_paths: list[str]
    may_authorize_edit: bool = False


class ContentPlatform(StrEnum):
    MEDIUM = "medium"
    LINKEDIN = "linkedin"
    X = "x"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    BLOG = "blog"


class ContentClaim(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    source_url: str | None = None
    source_title: str | None = None
    source_date: datetime | None = None
    provenance: Provenance


class ContentDraftCreate(BaseModel):
    platform: ContentPlatform
    title: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=100_000)
    claims: list[ContentClaim] = Field(default_factory=list)
    asset_ids: list[str] = Field(default_factory=list)
    target_account: str


class ContentDraft(ContentDraftCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: str = "draft"
    created_at: datetime = Field(default_factory=now_utc)


class PublicationEvidence(BaseModel):
    platform: ContentPlatform
    post_id: str | None = None
    public_url: str | None = None
    scheduled_url: str | None = None
    status: str | None = None


class MediaProvider(StrEnum):
    OPENAI = "openai"
    HIGGSFIELD = "higgsfield"
    LOCAL = "local"
    LICENSED_ASSET = "licensed_asset"


class MediaGenerationRequest(BaseModel):
    kind: str
    prompt: str = Field(min_length=1, max_length=4000)
    privacy: PrivacyClass = PrivacyClass.STANDARD
    requires_commercial_license: bool = True
    maximum_cost_usd: float | None = Field(default=None, ge=0)


class MediaRoute(BaseModel):
    provider: MediaProvider
    enabled: bool
    reason: str
    requires_external_call: bool


class StoryboardScene(BaseModel):
    index: int = Field(ge=0)
    narration: str
    visual_description: str
    duration_seconds: float = Field(gt=0)
    asset_ids: list[str] = Field(default_factory=list)


class VideoProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    platform: ContentPlatform
    aspect_ratio: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(gt=0, le=120)
    scenes: list[StoryboardScene] = Field(min_length=1)
    voice_provider: str = "elevenlabs"


class VideoProject(VideoProjectCreate):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    status: str = "storyboard"
    created_at: datetime = Field(default_factory=now_utc)


class VideoRenderEvidence(BaseModel):
    project_id: UUID
    output_path: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    fps: float | None = None
    audio_stream_present: bool = False
    captions_present: bool = False
    black_frame_count: int | None = None
    missing_assets: list[str] = Field(default_factory=list)
    text_clipping_detected: bool | None = None
    loudness_lufs: float | None = None


class FridayAgentState(BaseModel):
    user_id: UUID
    conversation_id: UUID
    session_id: UUID
    current_goal: str
    active_agent: str | None = None
    execution_status: ExecutionStatus = ExecutionStatus.UNDERSTANDING
    messages: list[dict[str, Any]] = Field(default_factory=list)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    verified_facts: list[Claim] = Field(default_factory=list)
    retrieved_memories: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_documents: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_web_sources: list[dict[str, Any]] = Field(default_factory=list)
    plan: list[dict[str, Any]] = Field(default_factory=list)
    current_step: int | None = None
    completed_steps: list[dict[str, Any]] = Field(default_factory=list)
    pending_steps: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    approval_requests: list[ActionRequest] = Field(default_factory=list)
    approval_results: list[Approval] = Field(default_factory=list)
    browser_state: dict[str, Any] | None = None
    repository_context: dict[str, Any] | None = None
    job_context: dict[str, Any] | None = None
    email_context: dict[str, Any] | None = None
    content_context: dict[str, Any] | None = None
    learning_context: dict[str, Any] | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    token_usage: dict[str, Any] = Field(default_factory=dict)
    estimated_cost: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)
    final_response: str | None = None
    verification_result: VerificationResult | None = None
