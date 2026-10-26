from hashlib import sha256
import logging
from datetime import UTC, datetime
from pathlib import Path
import json
import subprocess
from uuid import UUID
from uuid import UUID as CredentialUUID

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from friday.core.config import get_settings
from friday.core.redaction import redact
from friday.domain.models import (
    ActionRequest,
    Approval,
    ApprovalStatus,
    ApplicationDraft,
    ApplicationDraftCreate,
    ApplicationReview,
    AuditEvent,
    CalendarEvent,
    CalendarEventCreate,
    ContentDraft,
    ContentDraftCreate,
    Conversation,
    CandidateProfile,
    CredentialMetadata,
    EmailReplyDraft,
    EmailSignal,
    EmailThread,
    Message,
    MessageRole,
    MemoryProposal,
    MemoryProposalCreate,
    ModelRoute,
    ModelRouteRequest,
    Notification,
    NotificationCreate,
    Idea,
    IdeaCreate,
    JobPosting,
    JobAlertIngestionResult,
    JobMatch,
    GitOperationEvidence,
    KnowledgeSearchResult,
    LearningConcept,
    MediaGenerationRequest,
    MediaProvider,
    MediaRoute,
    Project,
    ProjectCreate,
    PublicationEvidence,
    ResumeClaim,
    ResumeClaimCreate,
    ResumeTailoringRequest,
    ResumeTailoringResult,
    RepositoryContext,
    RiskLevel,
    SessionGrant,
    StudySession,
    StudySessionCreate,
    Task,
    TaskCreate,
    TaskUpdate,
    UserSettings,
    UserSettingsUpdate,
    VideoProject,
    VideoProjectCreate,
    VideoRenderEvidence,
    VerifiedFact,
    VerifiedFactCreate,
    VoiceTranscriptAssessment,
)
from friday.services.policy import PolicyEngine
from friday.services.model_router import ModelRouter
from friday.services.store import store
from friday.services.voice import TranscriptValidator
from friday.services.persistence import PersistenceService
from friday.services.credentials import CredentialBroker, DevelopmentSecretResolver
from friday.services.notifications import NotificationService
from friday.services.settings import SettingsService
from friday.services.knowledge import KnowledgeService
from friday.services.qmd import QmdSearchService
from friday.services.jobs import GreenhouseAdapter, MicrosoftCareersAlertParser
from friday.services.jobs import JobCatalog, JobMatchingService
from friday.services.resume import ResumeService
from friday.services.applications import ApplicationService
from friday.services.communications import CalendarService, EmailService
from friday.services.content import ContentService
from friday.services.video import LocalVideoRenderer, MediaRouter, VideoService
from friday.services.local_auth import local_session_auth
from friday.services.learning import LearningService
from friday.services.device import MacOSDeviceService, ScopedFileService
from friday.services.github import GitExecutionService
from friday.services.coding import CodingSafetyService
from friday.services.browser import BrowserPolicy, ChromeFormWorker
from friday.services.oauth import LinkedInOAuthService
from friday.services.macos_keychain import MacOSKeychain
from friday.services.capabilities import CapabilityCatalog
from friday.services.attachments import AttachmentService
from friday.services.spotify import SpotifyService
from friday.services.gmail import GmailService
from friday.services.agents import AGENTS

router = APIRouter(prefix="/v1")
logger = logging.getLogger(__name__)
policy = PolicyEngine()
model_router = ModelRouter(get_settings())
transcript_validator = TranscriptValidator()
persistence = PersistenceService(get_settings(), store)
credential_broker = CredentialBroker(store, DevelopmentSecretResolver())
notification_service = NotificationService(store)
settings_service = SettingsService(store)
knowledge_service = KnowledgeService(store)
qmd_service = QmdSearchService()
resume_service = ResumeService()
application_service = ApplicationService()
email_service = EmailService()
calendar_service = CalendarService()
content_service = ContentService()
LINKEDIN_CREDENTIAL_ID = CredentialUUID("5f05dc9f-b8b9-4db4-8464-a8ee7b09be4e")
LINKEDIN_CONFIG_PATH = Path.cwd() / "artifacts" / "credentials" / "linkedin.json"
linkedin_keychain = MacOSKeychain()
_linkedin_secret = get_settings().linkedin_client_secret
_linkedin_config: dict[str, str] = {}
if LINKEDIN_CONFIG_PATH.exists():
    try:
        _linkedin_config = json.loads(LINKEDIN_CONFIG_PATH.read_text())
        _linkedin_secret_value = linkedin_keychain.load(LINKEDIN_CREDENTIAL_ID)
    except (OSError, ValueError, KeyError):
        _linkedin_config = {}
        _linkedin_secret_value = _linkedin_secret.get_secret_value() if _linkedin_secret else None
else:
    _linkedin_secret_value = _linkedin_secret.get_secret_value() if _linkedin_secret else None
linkedin_oauth = LinkedInOAuthService(
    _linkedin_config.get("client_id") or get_settings().linkedin_client_id,
    _linkedin_secret_value,
    _linkedin_config.get("redirect_uri") or get_settings().linkedin_redirect_uri,
)
linkedin_oauth.author_urn = _linkedin_config.get("author_urn") or get_settings().linkedin_author_urn
video_service = VideoService()
local_video_renderer = LocalVideoRenderer(Path.cwd() / "artifacts" / "videos")
media_router = MediaRouter({MediaProvider.OPENAI, MediaProvider.LOCAL})
job_catalog = JobCatalog()
learning_service = LearningService()
device_service = MacOSDeviceService()
file_service = ScopedFileService(
    [Path(value.strip()) for value in get_settings().authorized_file_roots.split(",") if value.strip()]
)
git_execution_service = GitExecutionService(Path.cwd())
coding_safety_service = CodingSafetyService(Path.cwd())
browser_policy = BrowserPolicy(
    {
        value.strip()
        for value in get_settings().allowed_browser_domains.split(",")
        if value.strip()
    },
    Path.cwd() / "artifacts" / "uploads",
)
chrome_form_worker = ChromeFormWorker(
    browser_policy,
    Path.cwd() / "artifacts" / "chrome-profile",
    Path.cwd() / "artifacts" / "browser-evidence",
    headless=get_settings().browser_headless,
)
attachment_service = AttachmentService(Path.cwd() / "artifacts" / "uploads" / "shared")
spotify_service = SpotifyService(get_settings().spotify_client_id, get_settings().spotify_redirect_uri)
gmail_service = GmailService(get_settings().gmail_client_id, get_settings().gmail_redirect_uri)
OAUTH_VAULT_PATH = Path.cwd() / "artifacts" / "credentials" / "oauth-vault.json"


def _load_oauth_vault() -> dict[str, str]:
    try:
        return json.loads(OAUTH_VAULT_PATH.read_text()) if OAUTH_VAULT_PATH.exists() else {}
    except (OSError, ValueError):
        return {}


def _save_oauth_vault(changes: dict[str, str | None]) -> None:
    values = _load_oauth_vault()
    values.update({key: value for key, value in changes.items() if value})
    OAUTH_VAULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OAUTH_VAULT_PATH.write_text(json.dumps(values))
    OAUTH_VAULT_PATH.chmod(0o600)


_oauth_vault = _load_oauth_vault()
spotify_service.access_token = _oauth_vault.get("spotify_access_token")
spotify_service.refresh_token = _oauth_vault.get("spotify_refresh_token")
gmail_service.client_secret = _oauth_vault.get("gmail_client_secret")
gmail_service.access_token = _oauth_vault.get("gmail_access_token")
gmail_service.refresh_token = _oauth_vault.get("gmail_refresh_token")


class DecisionBody(BaseModel):
    status: ApprovalStatus
    user_id: UUID


class ExecutionPreview(BaseModel):
    action: ActionRequest
    approval: Approval | None
    allowed: bool
    reason: str


class SessionCreate(BaseModel):
    user_id: UUID


class ConversationCreate(BaseModel):
    user_id: UUID
    title: str | None = None


class MessageCreate(BaseModel):
    conversation_id: UUID
    content: str


class ResponseCreate(BaseModel):
    conversation_id: UUID
    session_id: UUID
    content: str


class TranscriptBody(BaseModel):
    transcript: str = ""


class LinkedInConfigurationBody(BaseModel):
    client_id: str
    client_secret: str
    redirect_uri: str
    author_urn: str | None = None


class KnowledgeSearchBody(BaseModel):
    query: str
    collection: str
    limit: int = 5


class GreenhouseDiscoveryBody(BaseModel):
    board_token: str
    company: str


class JobMatchBody(BaseModel):
    job: JobPosting
    candidate: CandidateProfile


class EmailReplyBody(BaseModel):
    body: str


class LearningConceptBody(BaseModel):
    name: str


class OpenAppBody(BaseModel):
    app_name: str


class MediaControlBody(BaseModel):
    app_name: str
    command: str


class SpotifySearchBody(BaseModel):
    query: str


class BrowserReadBody(BaseModel):
    url: str


class CapabilityInspectBody(BaseModel):
    command: str


class GmailConfigurationBody(BaseModel):
    client_secret: str


class GitHubCloneBody(BaseModel):
    repository: str

class NewEmailDraftBody(BaseModel):
    recipients: list[str]
    subject: str
    body: str

class GitHubCreateBody(BaseModel):
    name: str
    description: str = ""
    visibility: str = "private"

class CodingTreeBody(BaseModel):
    path: str

class CodingFileCreateBody(BaseModel):
    root: str
    relative_path: str
    content: str = ""

class CodingCommandBody(BaseModel):
    command: list[str]

class CodingFileOpenBody(BaseModel):
    root: str
    relative_path: str

class CodingFileReplaceBody(CodingFileOpenBody):
    old_text: str
    new_text: str

active_coding_workspace: Path = Path.cwd().resolve()

def _authorized_coding_path(value: str) -> Path:
    candidate = Path(value).expanduser().resolve()
    roots = [Path.cwd().resolve(), Path("artifacts/repositories").resolve()]
    if not any(candidate == root or root in candidate.parents for root in roots):
        raise PermissionError("Path is outside Friday's authorized coding folders")
    return candidate


class GitHubRepositoryItem(BaseModel):
    name: str
    name_with_owner: str
    url: str
    description: str | None = None
    is_private: bool = False
    cloned_path: str | None = None


class FileReadBody(BaseModel):
    path: str


class DeviceEvidenceResponse(BaseModel):
    action: str
    target: str
    exit_code: int
    verified: bool


class GitCommitBody(BaseModel):
    message: str
    paths: list[str]


class BrowserFormBody(BaseModel):
    url: str
    fields: dict[str, str]
    submit_selector: str | None = None
    idempotency_key: str


class LinkedInComposeBody(BaseModel):
    topic: str
    audience: str
    key_points: list[str]
    call_to_action: str = ""
    target_account: str = "personal"
    tone: str = "clear"


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "friday-api"}


@router.get("/ready")
async def ready() -> dict[str, str]:
    settings = get_settings()
    if settings.persistence_backend == "memory":
        return {"status": "ready", "persistence": "memory"}
    if settings.persistence_backend != "postgresql":
        raise HTTPException(503, "Unsupported persistence backend")
    from friday.db.session import database_ready

    if not await database_ready():
        raise HTTPException(503, "PostgreSQL is unavailable")
    return {"status": "ready", "persistence": "postgresql"}


@router.post("/sessions", response_model=SessionGrant, status_code=201)
def create_session(payload: SessionCreate) -> SessionGrant:
    if payload.user_id != get_settings().local_user_id:
        raise HTTPException(403, "Only the configured local user can create a session")
    return local_session_auth.issue(store.create_session(payload.user_id))


@router.post("/conversations", response_model=Conversation, status_code=201)
def create_conversation(payload: ConversationCreate) -> Conversation:
    return store.create_conversation(payload.user_id, payload.title)


@router.post("/messages", response_model=Message, status_code=201)
def create_message(payload: MessageCreate) -> Message:
    try:
        return store.add_message(payload.conversation_id, MessageRole.USER, payload.content)
    except KeyError as exc:
        raise HTTPException(404, "Conversation not found") from exc


@router.post("/responses", response_model=Message, status_code=201)
async def create_response(payload: ResponseCreate) -> Message:
    settings = get_settings()
    if not settings.enable_model_calls:
        raise HTTPException(503, "Model calls are disabled; set FRIDAY_ENABLE_MODEL_CALLS=true")
    if payload.session_id not in store.sessions:
        raise HTTPException(404, "Session not found")
    if payload.conversation_id not in store.conversations:
        raise HTTPException(404, "Conversation not found")
    from friday.services.conversation import ConversationService
    from friday.services.events import event_hub
    from friday.services.generation import OpenAIResponsesGenerator

    try:
        service = ConversationService(
            store, model_router, OpenAIResponsesGenerator(settings), event_hub
        )
        return await service.respond(
            payload.conversation_id, payload.session_id, payload.content
        )
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/model-routes/preview", response_model=ModelRoute)
def preview_model_route(payload: ModelRouteRequest) -> ModelRoute:
    try:
        return model_router.route(payload)
    except ValueError as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/voice/transcripts/assess", response_model=VoiceTranscriptAssessment)
def assess_voice_transcript(payload: TranscriptBody) -> VoiceTranscriptAssessment:
    return transcript_validator.assess(payload.transcript)


@router.post("/voice/realtime/session", response_class=PlainTextResponse)
async def create_realtime_voice_session(request: Request) -> PlainTextResponse:
    """Exchange a browser WebRTC offer for a Realtime API answer without exposing the API key."""
    settings = get_settings()
    if not settings.enable_model_calls:
        raise HTTPException(503, "Voice model calls are disabled; set FRIDAY_ENABLE_MODEL_CALLS=true")
    if settings.openai_api_key is None:
        raise HTTPException(503, "OPENAI_API_KEY is not configured")
    offer = (await request.body()).decode("utf-8", errors="strict")
    if not offer.startswith("v=0") or len(offer) > 100_000:
        raise HTTPException(422, "Invalid WebRTC session description")
    agent_manifest = "; ".join(f"{agent.name}: {agent.purpose} [{', '.join(sorted(agent.tool_groups)) or 'routing only'}]" for agent in AGENTS)
    session = {
        "type": "realtime",
        "model": settings.model_realtime,
        "instructions": (
            f"You are Friday, {settings.user_display_name}'s concise, warm desktop assistant. Converse naturally. "
            "You supervise the following defined agents and capabilities: " + agent_manifest + ". "
            f"The active coding workspace is {active_coding_workspace}. Use it when the user says this repo, current project, run tests, edit a file, or open in VS Code. "
            "Choose the matching declared tool when one is available. If a capability exists but its execution tool or authorization is unavailable, say setup is required and name the correct agent; never say no agents are connected. "
            "Never claim an external action completed without verified evidence. Ask before risky actions."
        ),
        "audio": {
            "input": {
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.3,
                    "prefix_padding_ms": 400,
                    "silence_duration_ms": 700,
                    "create_response": True,
                    "interrupt_response": True,
                },
                "noise_reduction": {"type": "near_field"},
                "transcription": {
                    "model": "gpt-4o-mini-transcribe",
                    "language": "en",
                    "prompt": "The user is speaking commands to Friday on a Mac. Common phrases include: open Spotify, play music on Spotify, sync Gmail, summarize my email, create a task, open Chrome, and create a LinkedIn post.",
                },
            },
            "output": {"voice": "marin"},
        },
        "tools": [
            {
                "type": "function", "name": "describe_friday_capabilities",
                "description": "Return Friday's complete defined agent and capability registry when the user asks what Friday can do or which agents are available.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "type": "function", "name": "create_youtube_short_project",
                "description": "Create a visible 9:16 YouTube Shorts video project in Friday. This creates the storyboard project but does not upload it.",
                "parameters": {"type": "object", "properties": {"title": {"type": "string"}, "narration": {"type": "string"}}, "required": ["title", "narration"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "analyze_current_repository",
                "description": "Inspect the currently authorized Git repository and return its branch and changed files without modifying it.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "type": "function", "name": "list_github_repositories",
                "description": "Retrieve the connected GitHub account's repository inventory and show it in Friday's Coding section.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {"type": "function", "name": "clone_github_repository", "description": "Clone a repository from the connected GitHub account into Friday's local artifacts/repositories folder.", "parameters": {"type": "object", "properties": {"repository": {"type": "string"}}, "required": ["repository"], "additionalProperties": False}},
            {"type": "function", "name": "open_local_coding_folder", "description": "Open an authorized local Friday workspace or cloned repository folder in macOS Finder.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}},
            {"type": "function", "name": "visualize_repository_structure", "description": "Read and show the folder and file structure of an authorized local repository in Friday's Coding workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}},
            {"type": "function", "name": "save_file_in_repository", "description": "Create or edit a text file inside an authorized Friday workspace or cloned repository.", "parameters": {"type": "object", "properties": {"root": {"type": "string"}, "relative_path": {"type": "string"}, "content": {"type": "string"}}, "required": ["root", "relative_path", "content"], "additionalProperties": False}},
            {"type": "function", "name": "select_active_repository", "description": "Select an authorized local Git repository as Friday's active coding workspace.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"], "additionalProperties": False}},
            {"type": "function", "name": "open_active_repository_in_vscode", "description": "Open Friday's active repository in Visual Studio Code.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"type": "function", "name": "open_file_in_vscode", "description": "Open a specific existing file from an authorized repository in Visual Studio Code.", "parameters": {"type": "object", "properties": {"root": {"type": "string"}, "relative_path": {"type": "string"}}, "required": ["root", "relative_path"], "additionalProperties": False}},
            {"type": "function", "name": "read_repository_file", "description": "Read an existing text file from an authorized repository before proposing or applying an edit.", "parameters": {"type": "object", "properties": {"root": {"type": "string"}, "relative_path": {"type": "string"}}, "required": ["root", "relative_path"], "additionalProperties": False}},
            {"type": "function", "name": "replace_text_in_repository_file", "description": "Modify a repository file by replacing one exact, unique text block with new text and return verified edit evidence.", "parameters": {"type": "object", "properties": {"root": {"type": "string"}, "relative_path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["root", "relative_path", "old_text", "new_text"], "additionalProperties": False}},
            {"type": "function", "name": "run_safe_repository_command", "description": "Run a safe test, build, formatting, lint, or read-only Git command in the active repository.", "parameters": {"type": "object", "properties": {"command": {"type": "array", "items": {"type": "string"}}}, "required": ["command"], "additionalProperties": False}},
            {"type": "function", "name": "request_git_push_approval", "description": "Prepare pushing the active repository's current branch to origin and request approve-once authorization.", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
            {"type": "function", "name": "execute_approved_git_push", "description": "Push the active repository's current branch to origin using a matching approved-once approval ID and return remote commit evidence.", "parameters": {"type": "object", "properties": {"approval_id": {"type": "string"}}, "required": ["approval_id"], "additionalProperties": False}},
            {
                "type": "function", "name": "request_github_repository_creation",
                "description": "Prepare creation of a new repository in the connected GitHub account and request approve-once authorization. Do not claim it is created until execution evidence exists.",
                "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}, "visibility": {"type": "string", "enum": ["private", "public"]}}, "required": ["name", "visibility"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "execute_approved_github_repository_creation",
                "description": "Execute a previously approved GitHub repository creation using its approve-once approval ID and return the verified repository URL.",
                "parameters": {"type": "object", "properties": {"approval_id": {"type": "string"}}, "required": ["approval_id"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "create_learning_plan_topic",
                "description": "Create a visible learning concept in Friday as the starting point for a learning plan.",
                "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "read_approved_webpage",
                "description": "Read an approved public webpage using Friday's governed browser adapter.",
                "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"], "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "create_task",
                "description": "Create a real task in Friday and make it visible in the Tasks workspace.",
                "parameters": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "summarize_available_email",
                "description": "Inspect email threads currently connected to Friday and summarize today's available messages. If none are connected, report that setup is missing.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "create_email_reply_draft",
                "description": "Create a visible email reply draft for an existing Friday email thread. This does not send it; sending requires approval and a connected provider.",
                "parameters": {
                    "type": "object",
                    "properties": {"thread_id": {"type": "string"}, "body": {"type": "string"}},
                    "required": ["thread_id", "body"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function", "name": "create_new_email_draft",
                "description": "Create a visible brand-new Gmail draft with recipients, subject, and body. This does not send it.",
                "parameters": {"type": "object", "properties": {"recipients": {"type": "array", "items": {"type": "string"}}, "subject": {"type": "string"}, "body": {"type": "string"}}, "required": ["recipients", "subject", "body"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "request_email_send_approval",
                "description": "Create an approve-once authorization request for an existing Friday email draft.",
                "parameters": {"type": "object", "properties": {"draft_id": {"type": "string"}}, "required": ["draft_id"], "additionalProperties": False},
            },
            {
                "type": "function", "name": "execute_approved_email_send",
                "description": "Send an email draft through connected Gmail using its matching approved-once approval ID and return Gmail message evidence.",
                "parameters": {"type": "object", "properties": {"draft_id": {"type": "string"}, "approval_id": {"type": "string"}}, "required": ["draft_id", "approval_id"], "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "open_spotify",
                "description": "Open the Spotify desktop application on this Mac. Use this when the user asks to open, launch, or show Spotify without naming music to play.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
            {
                "type": "function",
                "name": "spotify_search",
                "description": "Open Spotify and immediately play a requested song, artist, album, or playlist on the available Spotify device.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "type": "function",
                "name": "create_linkedin_draft",
                "description": "Create and save a copyable LinkedIn post draft in Friday's Content workspace. Use this instead of only reciting proposed post text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "audience": {"type": "string"},
                        "key_points": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 8},
                        "call_to_action": {"type": "string"},
                        "tone": {"type": "string", "enum": ["clear", "bold", "reflective"]},
                    },
                    "required": ["topic", "audience", "key_points", "call_to_action", "tone"],
                    "additionalProperties": False,
                },
            },
        ],
        "tool_choice": "auto",
    }
    safety_id = sha256(str(settings.local_user_id).encode()).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key.get_secret_value()}",
                    "OpenAI-Safety-Identifier": safety_id,
                },
                files={
                    "sdp": (None, offer),
                    "session": (None, __import__("json").dumps(session)),
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Realtime voice provider is unavailable") from exc
    if not response.is_success:
        error_code = "unknown"
        try:
            error_code = str(response.json().get("error", {}).get("code") or response.json().get("error", {}).get("type") or "unknown")
        except (ValueError, AttributeError):
            pass
        logger.warning("Realtime provider rejected session: status=%s code=%s", response.status_code, error_code)
        if error_code == "insufficient_quota":
            raise HTTPException(402, "OpenAI API billing or project limit requires attention")
        raise HTTPException(502, f"Realtime voice session failed ({response.status_code})")
    return PlainTextResponse(response.text, media_type="application/sdp")


@router.post("/tasks", response_model=Task, status_code=201)
async def create_task(payload: TaskCreate) -> Task:
    return await persistence.create_task(payload)


@router.get("/tasks", response_model=list[Task])
async def list_tasks() -> list[Task]:
    return await persistence.list_tasks()


@router.patch("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: UUID, payload: TaskUpdate) -> Task:
    try:
        return await persistence.update_task(task_id, payload)
    except KeyError as exc:
        raise HTTPException(404, "Task not found") from exc


@router.post("/actions/preview", response_model=ExecutionPreview)
def preview_action(action: ActionRequest) -> ExecutionPreview:
    try:
        approval = store.create_action(action)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    store.append_audit(
        AuditEvent(
            event_type="action.previewed",
            actor=action.agent,
            target_type="action",
            target_id=str(action.id),
            safe_payload=redact(
                {"action": action.action, "target": action.target, "risk": int(action.risk)}
            ),
        )
    )
    decision = policy.evaluate(action)
    return ExecutionPreview(
        action=action, approval=approval, allowed=decision.allowed, reason=decision.reason
    )


@router.get("/approvals", response_model=list[Approval])
def list_approvals() -> list[Approval]:
    return list(store.approvals.values())


@router.get("/audit-events", response_model=list[AuditEvent])
async def list_audit_events() -> list[AuditEvent]:
    return await persistence.list_audit_events()


@router.post("/approvals/{approval_id}/decision", response_model=Approval)
def decide_approval(approval_id: UUID, body: DecisionBody) -> Approval:
    if body.status not in {ApprovalStatus.APPROVED_ONCE, ApprovalStatus.REJECTED}:
        raise HTTPException(422, "Only approve-once or reject is supported by this endpoint")
    try:
        approval = store.decide(approval_id, body.status, body.user_id)
    except KeyError as exc:
        raise HTTPException(404, "Approval not found") from exc
    store.append_audit(
        AuditEvent(
            user_id=body.user_id,
            event_type=f"approval.{body.status}",
            actor="user",
            target_type="approval",
            target_id=str(approval.id),
            safe_payload={"action_id": str(approval.action_id), "scope": approval.scope},
        )
    )
    return approval


@router.get("/risk-levels")
def risk_levels() -> dict[str, int]:
    return {level.name.lower(): int(level) for level in RiskLevel}


@router.post("/device/apps/open", response_model=DeviceEvidenceResponse)
def open_device_app(payload: OpenAppBody) -> DeviceEvidenceResponse:
    try:
        return DeviceEvidenceResponse(**device_service.open_app(payload.app_name).__dict__)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc


@router.post("/device/media/control", response_model=DeviceEvidenceResponse)
def control_device_media(payload: MediaControlBody) -> DeviceEvidenceResponse:
    try:
        return DeviceEvidenceResponse(
            **device_service.media_control(payload.app_name, payload.command).__dict__
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/device/spotify/search", response_model=DeviceEvidenceResponse)
def search_spotify(payload: SpotifySearchBody) -> DeviceEvidenceResponse:
    try:
        if not spotify_service.connected:
            raise PermissionError("Reconnect Spotify before requesting playback")
        track = spotify_service.search_and_play(payload.query)
        return DeviceEvidenceResponse(action="spotify_play", target=f"{track['name']} — {track['artist']}", exit_code=0, verified=True)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except (httpx.HTTPStatusError, RuntimeError) as exc:
        logger.warning("Spotify playback failed: %s", str(exc))
        raise HTTPException(502, "Spotify playback failed; ensure Premium and an active device") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/oauth/spotify/status")
def spotify_status() -> dict[str, bool]:
    return {"configured": bool(spotify_service.client_id), "connected": spotify_service.connected}


@router.get("/oauth/spotify/start")
def spotify_start() -> RedirectResponse:
    return RedirectResponse(spotify_service.authorization_url())


@router.get("/oauth/spotify/callback", response_class=PlainTextResponse)
def spotify_callback(code: str, state: str) -> str:
    try:
        spotify_service.exchange(code, state)
        _save_oauth_vault({"spotify_access_token": spotify_service.access_token, "spotify_refresh_token": spotify_service.refresh_token})
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Spotify authorization failed") from exc
    return "Spotify connected to Friday. You may close this window."


@router.get("/oauth/gmail/status")
def gmail_status() -> dict[str, bool]:
    return {"configured": bool(gmail_service.client_id and gmail_service.client_secret), "connected": gmail_service.connected}


@router.post("/oauth/gmail/configure")
def gmail_configure(payload: GmailConfigurationBody) -> dict[str, bool]:
    try:
        gmail_service.configure(payload.client_secret)
        _save_oauth_vault({"gmail_client_secret": payload.client_secret})
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {"configured": True, "connected": False}


@router.get("/oauth/gmail/start")
def gmail_start() -> RedirectResponse:
    return RedirectResponse(gmail_service.authorization_url())


@router.get("/oauth/gmail/callback", response_class=PlainTextResponse)
def gmail_callback(code: str, state: str) -> str:
    try:
        gmail_service.exchange(code, state)
        _save_oauth_vault({"gmail_access_token": gmail_service.access_token, "gmail_refresh_token": gmail_service.refresh_token})
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (httpx.HTTPError, RuntimeError) as exc:
        logger.warning("Gmail authorization failed: %s", str(exc))
        raise HTTPException(502, "Gmail authorization failed") from exc
    return "Gmail connected to Friday. You may close this window."


@router.post("/email/gmail/sync", response_model=list[EmailThread])
def sync_gmail() -> list[EmailThread]:
    try:
        threads = gmail_service.recent_threads(get_settings().local_user_id)
        return [email_service.ingest_thread(thread) for thread in threads]
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Gmail synchronization failed") from exc


@router.post("/browser/read")
async def read_browser_page(payload: BrowserReadBody) -> dict[str, object]:
    try:
        return await chrome_form_worker.read_page(payload.url)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/capabilities/inspect")
def inspect_capability(payload: CapabilityInspectBody) -> dict[str, object]:
    return CapabilityCatalog(Path.cwd(), linkedin_oauth.connected).inspect(payload.command)


@router.post("/attachments")
async def upload_attachment(request: Request) -> dict[str, object]:
    filename = request.headers.get("x-friday-filename", "")
    content_type = request.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
    content_length = int(request.headers.get("content-length", "0") or 0)
    if content_length > AttachmentService.MAX_BYTES:
        raise HTTPException(413, "Attachment exceeds 100 MB")
    try:
        return attachment_service.store(filename, content_type, await request.body())
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/files/search")
def search_authorized_files(query: str, limit: int = 50) -> list[dict[str, object]]:
    try:
        return file_service.search(query, limit)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/files/read")
def read_authorized_text_file(payload: FileReadBody) -> dict[str, object]:
    try:
        return file_service.read_text(payload.path)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "File not found") from exc
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/coding/git/commit", response_model=GitOperationEvidence)
def create_local_git_commit(payload: GitCommitBody) -> GitOperationEvidence:
    try:
        evidence = git_execution_service.commit(payload.message, payload.paths)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        logger.exception("Verified local Git commit failed")
        raise HTTPException(500, str(exc)) from exc
    store.append_audit(
        AuditEvent(
            event_type="git.commit.verified",
            actor="coding",
            target_type="repository",
            target_id=evidence.local_commit,
            safe_payload={"paths": payload.paths, "commit": evidence.local_commit},
        )
    )
    return evidence


@router.get("/coding/repository", response_model=RepositoryContext)
def inspect_coding_repository() -> RepositoryContext:
    try:
        return coding_safety_service.inspect_repository()
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc

@router.post("/coding/tree")
def coding_tree(payload: CodingTreeBody) -> dict[str, object]:
    try: root = _authorized_coding_path(payload.path)
    except PermissionError as exc: raise HTTPException(403, str(exc)) from exc
    if not root.is_dir(): raise HTTPException(404, "Repository folder not found")
    entries=[]
    for item in sorted(root.rglob("*")):
        relative=item.relative_to(root)
        if any(part in {".git","node_modules","target",".venv"} for part in relative.parts): continue
        if len(relative.parts)>5 or len(entries)>=500: continue
        entries.append({"path":str(relative),"kind":"folder" if item.is_dir() else "file","size":item.stat().st_size if item.is_file() else 0})
    return {"root":str(root),"entries":entries}

@router.post("/coding/files", status_code=201)
def create_coding_file(payload: CodingFileCreateBody) -> dict[str, object]:
    try: root=_authorized_coding_path(payload.root)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    target=(root/payload.relative_path).resolve()
    if root not in target.parents or target.name in {".env",".env.local"}: raise HTTPException(403,"File path is not allowed")
    if target.exists(): raise HTTPException(409,"File already exists; use the coding agent to edit it")
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(payload.content,encoding="utf-8")
    return {"path":str(target),"relative_path":str(target.relative_to(root)),"bytes":target.stat().st_size,"created":True}

@router.post("/coding/folders/open")
def open_coding_folder(payload: CodingTreeBody) -> dict[str, object]:
    try: path=_authorized_coding_path(payload.path)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    if not path.is_dir(): raise HTTPException(404,"Folder not found")
    result=subprocess.run(["open",str(path)],capture_output=True,timeout=10)
    return {"path":str(path),"opened":result.returncode==0}

@router.post("/coding/workspace/select")
def select_coding_workspace(payload: CodingTreeBody) -> dict[str, object]:
    global active_coding_workspace
    try: path=_authorized_coding_path(payload.path)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    if not (path/".git").is_dir(): raise HTTPException(422,"Selected folder is not a Git repository")
    active_coding_workspace=path
    return {"path":str(path),"selected":True}

@router.get("/coding/workspace")
def get_coding_workspace() -> dict[str, object]:
    result=subprocess.run(["git","status","--short","--branch"],cwd=active_coding_workspace,capture_output=True,text=True,timeout=10)
    return {"path":str(active_coding_workspace),"git":result.stdout,"ready":result.returncode==0}

@router.post("/coding/workspace/open-vscode")
def open_workspace_vscode() -> dict[str, object]:
    result=subprocess.run(["open","-a","Visual Studio Code",str(active_coding_workspace)],capture_output=True,timeout=10)
    return {"path":str(active_coding_workspace),"opened":result.returncode==0,"application":"Visual Studio Code"}

@router.post("/coding/files/open-vscode")
def open_file_vscode(payload: CodingFileOpenBody) -> dict[str, object]:
    try: root=_authorized_coding_path(payload.root)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    target=(root/payload.relative_path).resolve()
    if root not in target.parents or not target.is_file(): raise HTTPException(404,"Authorized file not found")
    result=subprocess.run(["open","-a","Visual Studio Code",str(target)],capture_output=True,timeout=10)
    return {"path":str(target),"relative_path":str(target.relative_to(root)),"opened":result.returncode==0,"application":"Visual Studio Code"}

@router.post("/coding/files/read")
def read_coding_file(payload: CodingFileOpenBody) -> dict[str, object]:
    try: root=_authorized_coding_path(payload.root)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    target=(root/payload.relative_path).resolve()
    if root not in target.parents or not target.is_file() or target.stat().st_size>2_000_000: raise HTTPException(404,"Readable repository file not found")
    return {"path":str(target),"relative_path":str(target.relative_to(root)),"content":target.read_text(encoding="utf-8"),"bytes":target.stat().st_size}

@router.patch("/coding/files")
def replace_coding_file_text(payload: CodingFileReplaceBody) -> dict[str, object]:
    data=read_coding_file(CodingFileOpenBody(root=payload.root,relative_path=payload.relative_path)); content=str(data["content"])
    if not payload.old_text or content.count(payload.old_text)!=1: raise HTTPException(409,"Edit target must match exactly once")
    updated=content.replace(payload.old_text,payload.new_text,1); Path(str(data["path"])).write_text(updated,encoding="utf-8")
    return {"path":data["path"],"relative_path":data["relative_path"],"edited":True,"bytes":len(updated.encode()),"replacements":1}

@router.post("/coding/workspace/command")
def run_workspace_command(payload: CodingCommandBody) -> dict[str, object]:
    allowed={"git","npm","npx","pytest","python","python3","ruff","cargo"}
    if not payload.command or payload.command[0] not in allowed or any(value in {"push","reset","clean","publish","install","uninstall"} for value in payload.command): raise HTTPException(403,"Command is outside Friday's safe terminal allowlist")
    result=subprocess.run(payload.command,cwd=active_coding_workspace,capture_output=True,text=True,timeout=120)
    return {"command":payload.command,"cwd":str(active_coding_workspace),"exit_code":result.returncode,"stdout":result.stdout[-12000:],"stderr":result.stderr[-4000:],"verified":result.returncode==0}

@router.post("/coding/git/push-preview", response_model=ExecutionPreview)
def preview_active_git_push() -> ExecutionPreview:
    branch=subprocess.run(["git","branch","--show-current"],cwd=active_coding_workspace,capture_output=True,text=True,timeout=10).stdout.strip()
    commit=subprocess.run(["git","rev-parse","HEAD"],cwd=active_coding_workspace,capture_output=True,text=True,timeout=10).stdout.strip()
    if not branch or not commit: raise HTTPException(409,"Active repository has no pushable branch or commit")
    action=ActionRequest(agent="github",action="git_push",target=f"origin/{branch}",risk=RiskLevel.HIGH_IMPACT,data_transmitted=["commits","branch"],reversible=False,expected_outcome="Remote branch points to the local HEAD commit",idempotency_key=f"git-push:{active_coding_workspace}:{branch}:{commit}",preview={"root":str(active_coding_workspace),"branch":branch,"commit":commit})
    approval=store.create_action(action); decision=policy.evaluate(action)
    return ExecutionPreview(action=action,approval=approval,allowed=decision.allowed,reason=decision.reason)

@router.post("/coding/git/push/{approval_id}")
def execute_active_git_push(approval_id: UUID) -> dict[str, object]:
    try: approval=store.approvals[approval_id]; action=store.actions[approval.action_id]
    except KeyError as exc: raise HTTPException(404,"Push approval not found") from exc
    if approval.status!=ApprovalStatus.APPROVED_ONCE or action.action!="git_push": raise HTTPException(403,"Git push requires matching approve-once authorization")
    root=Path(str(action.preview["root"])); branch=str(action.preview["branch"]); expected=str(action.preview["commit"])
    current=subprocess.run(["git","rev-parse","HEAD"],cwd=root,capture_output=True,text=True,timeout=10).stdout.strip()
    if current!=expected: raise HTTPException(409,"Repository changed after approval; request a new push approval")
    result=subprocess.run(["git","push","-u","origin",branch],cwd=root,capture_output=True,text=True,timeout=120)
    if result.returncode!=0: raise HTTPException(502,"GitHub push failed")
    remote=subprocess.run(["git","ls-remote","origin",f"refs/heads/{branch}"],cwd=root,capture_output=True,text=True,timeout=30).stdout.split()
    remote_commit=remote[0] if remote else ""
    return {"root":str(root),"branch":branch,"local_commit":expected,"remote_commit":remote_commit,"verified":remote_commit==expected}

@router.put("/coding/files")
def save_coding_file(payload: CodingFileCreateBody) -> dict[str, object]:
    try: root=_authorized_coding_path(payload.root)
    except PermissionError as exc: raise HTTPException(403,str(exc)) from exc
    target=(root/payload.relative_path).resolve()
    if root not in target.parents or target.name in {".env",".env.local"} or ".git" in target.parts: raise HTTPException(403,"File path is not allowed")
    existed=target.exists()
    if existed and (not target.is_file() or target.stat().st_size>2_000_000): raise HTTPException(409,"Only text files up to 2 MB can be edited")
    target.parent.mkdir(parents=True,exist_ok=True); target.write_text(payload.content,encoding="utf-8")
    return {"path":str(target),"relative_path":str(target.relative_to(root)),"bytes":target.stat().st_size,"created":not existed,"edited":existed}


def _connected_github_owner() -> str:
    configured = get_settings().github_owner.strip()
    if configured:
        return configured
    result = subprocess.run(
        ["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True, timeout=15
    )
    owner = result.stdout.strip()
    if result.returncode != 0 or not owner:
        raise HTTPException(401, "GitHub authorization is unavailable; run gh auth login")
    return owner


@router.get("/github/repositories", response_model=list[GitHubRepositoryItem])
def list_github_repositories() -> list[GitHubRepositoryItem]:
    owner = _connected_github_owner()
    result = subprocess.run(
        ["gh", "repo", "list", owner, "--limit", "100", "--json", "name,nameWithOwner,url,description,isPrivate"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        raise HTTPException(401, "GitHub authorization is unavailable")
    clone_root = Path("artifacts/repositories").resolve()
    return [GitHubRepositoryItem(
        name=item["name"], name_with_owner=item["nameWithOwner"], url=item["url"],
        description=item.get("description"), is_private=bool(item.get("isPrivate")),
        cloned_path=str(clone_root / item["name"]) if (clone_root / item["name"]).is_dir() else None,
    ) for item in json.loads(result.stdout)]


@router.post("/github/repositories/clone", response_model=GitHubRepositoryItem)
def clone_github_repository(payload: GitHubCloneBody) -> GitHubRepositoryItem:
    owner = _connected_github_owner()
    repository = payload.repository if "/" in payload.repository else f"{owner}/{payload.repository}"
    if not repository.startswith(f"{owner}/"):
        raise HTTPException(403, "Only repositories from the connected GitHub account may be cloned here")
    name = repository.split("/", 1)[1]
    if not name or any(value in name for value in ("/", "..", "\\")):
        raise HTTPException(422, "Invalid repository name")
    clone_root = Path("artifacts/repositories").resolve()
    clone_root.mkdir(parents=True, exist_ok=True)
    destination = clone_root / name
    if destination.exists():
        raise HTTPException(409, "Repository is already cloned")
    result = subprocess.run(["gh", "repo", "clone", repository, str(destination)], capture_output=True, text=True, timeout=180)
    if result.returncode != 0:
        raise HTTPException(502, "GitHub clone failed")
    return GitHubRepositoryItem(name=name, name_with_owner=repository, url=f"https://github.com/{repository}", cloned_path=str(destination))

@router.post("/github/repositories/create-preview", response_model=ExecutionPreview)
def preview_github_repository_create(payload: GitHubCreateBody) -> ExecutionPreview:
    if payload.visibility not in {"private", "public"} or not payload.name or any(value in payload.name for value in ("/", "..", " ")):
        raise HTTPException(422, "Repository name or visibility is invalid")
    owner = _connected_github_owner()
    action = ActionRequest(agent="github", action="create_repository", target=f"{owner}/{payload.name}", risk=RiskLevel.HIGH_IMPACT, data_transmitted=["name", "description", "visibility"], reversible=False, expected_outcome="GitHub returns the new repository URL", idempotency_key=f"github-create:{payload.name}", preview=payload.model_dump())
    approval = store.create_action(action)
    decision = policy.evaluate(action)
    return ExecutionPreview(action=action, approval=approval, allowed=decision.allowed, reason=decision.reason)

@router.post("/github/repositories/create/{approval_id}", response_model=GitHubRepositoryItem)
def create_github_repository(approval_id: UUID) -> GitHubRepositoryItem:
    try:
        approval, action = store.approvals[approval_id], store.actions[store.approvals[approval_id].action_id]
    except KeyError as exc:
        raise HTTPException(404, "Repository approval not found") from exc
    if approval.status != ApprovalStatus.APPROVED_ONCE or action.action != "create_repository":
        raise HTTPException(403, "Repository creation requires matching approve-once authorization")
    values = action.preview
    result = subprocess.run(["gh", "repo", "create", str(values["name"]), f"--{values['visibility']}", "--description", str(values.get("description", ""))], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise HTTPException(502, "GitHub repository creation failed")
    owner = _connected_github_owner()
    url = result.stdout.strip() or f"https://github.com/{owner}/{values['name']}"
    return GitHubRepositoryItem(name=str(values["name"]), name_with_owner=f"{owner}/{values['name']}", url=url, description=str(values.get("description", "")), is_private=values["visibility"] == "private")


@router.post("/browser/forms/preview")
async def preview_browser_form(payload: BrowserFormBody) -> dict[str, object]:
    try:
        preview = await chrome_form_worker.fill_preview(
            payload.url,
            payload.fields,
            f"preview-{payload.idempotency_key}",
        )
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    approval = None
    if payload.submit_selector:
        action = ActionRequest(
            agent="browser",
            action="browser_form_submit",
            target=payload.url,
            risk=RiskLevel.EXTERNAL_COMMUNICATION,
            data_transmitted=sorted(payload.fields),
            reversible=False,
            expected_outcome="Form submitted with provider confirmation evidence",
            idempotency_key=payload.idempotency_key,
            preview={
                "url": payload.url,
                "fields": payload.fields,
                "submit_selector": payload.submit_selector,
            },
        )
        try:
            approval = store.create_action(action)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    return {"preview": preview, "approval": approval.model_dump(mode="json") if approval else None}


@router.post("/browser/forms/{approval_id}/submit")
async def submit_approved_browser_form(approval_id: UUID) -> dict[str, object]:
    try:
        approval = store.approvals[approval_id]
        action = store.actions[approval.action_id]
    except KeyError as exc:
        raise HTTPException(404, "Browser submission approval not found") from exc
    if approval.status != ApprovalStatus.APPROVED_ONCE:
        raise HTTPException(403, "Browser form submission requires approve-once authorization")
    if action.action != "browser_form_submit":
        raise HTTPException(409, "Approval does not authorize browser form submission")
    browser_policy.register_approved_submission(action.idempotency_key)
    preview = action.preview
    try:
        result = await chrome_form_worker.fill_preview(
            str(preview["url"]),
            dict(preview["fields"]),
            f"submit-{action.idempotency_key}",
            submit_selector=str(preview["submit_selector"]),
        )
    except (PermissionError, ValueError, RuntimeError) as exc:
        raise HTTPException(409, str(exc)) from exc
    verified = bool(
        result.get("confirmation_detected")
        or result.get("resulting_url") != result.get("url")
    )
    store.append_audit(
        AuditEvent(
            event_type="browser.form.submitted" if verified else "browser.form.unverified",
            actor="browser",
            target_type="url",
            target_id=str(result.get("resulting_url")),
            safe_payload={
                "field_names": sorted(dict(preview["fields"])),
                "verified": verified,
                "evidence": result.get("screenshot_path"),
            },
        )
    )
    return {**result, "verified": verified}


@router.get("/credentials/metadata", response_model=list[CredentialMetadata])
def list_credential_metadata() -> list[CredentialMetadata]:
    return credential_broker.list_safe_metadata(get_settings().local_user_id)


@router.post("/notifications", response_model=Notification, status_code=201)
def create_notification(payload: NotificationCreate) -> Notification:
    return notification_service.create(get_settings().local_user_id, payload)


@router.get("/notifications", response_model=list[Notification])
def list_notifications() -> list[Notification]:
    return notification_service.list_for_user(get_settings().local_user_id)


@router.post("/notifications/{notification_id}/read", response_model=Notification)
def mark_notification_read(notification_id: UUID) -> Notification:
    try:
        return notification_service.mark_read(get_settings().local_user_id, notification_id)
    except KeyError as exc:
        raise HTTPException(404, "Notification not found") from exc


@router.post("/notifications/{notification_id}/dismiss", response_model=Notification)
def dismiss_notification(notification_id: UUID) -> Notification:
    try:
        return notification_service.dismiss(get_settings().local_user_id, notification_id)
    except KeyError as exc:
        raise HTTPException(404, "Notification not found") from exc


@router.get("/settings", response_model=UserSettings)
def get_user_settings() -> UserSettings:
    return settings_service.get(get_settings().local_user_id)


@router.patch("/settings", response_model=UserSettings)
def update_user_settings(payload: UserSettingsUpdate) -> UserSettings:
    return settings_service.update(get_settings().local_user_id, payload)


@router.post("/projects", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate) -> Project:
    return knowledge_service.create_project(get_settings().local_user_id, payload)


@router.get("/projects", response_model=list[Project])
def list_projects() -> list[Project]:
    user_id = get_settings().local_user_id
    return [item for item in knowledge_service.projects.values() if item.user_id == user_id]


@router.post("/ideas", response_model=Idea, status_code=201)
def create_idea(payload: IdeaCreate) -> Idea:
    return knowledge_service.create_idea(get_settings().local_user_id, payload)


@router.get("/ideas", response_model=list[Idea])
def list_ideas() -> list[Idea]:
    user_id = get_settings().local_user_id
    return [item for item in knowledge_service.ideas.values() if item.user_id == user_id]


@router.post("/facts", response_model=VerifiedFact, status_code=201)
def register_verified_fact(payload: VerifiedFactCreate) -> VerifiedFact:
    try:
        return knowledge_service.register_fact(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/facts", response_model=list[VerifiedFact])
def list_verified_facts() -> list[VerifiedFact]:
    user_id = get_settings().local_user_id
    return [item for item in knowledge_service.facts.values() if item.user_id == user_id]


@router.post("/memories/proposals", response_model=MemoryProposal, status_code=201)
def propose_memory(payload: MemoryProposalCreate) -> MemoryProposal:
    return knowledge_service.propose_memory(get_settings().local_user_id, payload)


@router.get("/memories/proposals", response_model=list[MemoryProposal])
def list_memory_proposals() -> list[MemoryProposal]:
    user_id = get_settings().local_user_id
    return [item for item in knowledge_service.memories.values() if item.user_id == user_id]


@router.post("/memories/{memory_id}/approve", response_model=MemoryProposal)
def approve_memory(memory_id: UUID) -> MemoryProposal:
    try:
        return knowledge_service.decide_memory(
            get_settings().local_user_id, memory_id, approve=True
        )
    except KeyError as exc:
        raise HTTPException(404, "Memory not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/memories/{memory_id}/reject", response_model=MemoryProposal)
def reject_memory(memory_id: UUID) -> MemoryProposal:
    try:
        return knowledge_service.decide_memory(
            get_settings().local_user_id, memory_id, approve=False
        )
    except KeyError as exc:
        raise HTTPException(404, "Memory not found") from exc


@router.post("/knowledge/search", response_model=KnowledgeSearchResult)
def search_knowledge(payload: KnowledgeSearchBody) -> KnowledgeSearchResult:
    try:
        return qmd_service.search(payload.query, payload.collection, payload.limit)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(503, str(exc)) from exc


@router.post("/jobs/greenhouse/discover", response_model=list[JobPosting])
async def discover_greenhouse_jobs(payload: GreenhouseDiscoveryBody) -> list[JobPosting]:
    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            postings = await GreenhouseAdapter(client).fetch(payload.board_token, payload.company)
            return job_catalog.ingest(postings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Greenhouse discovery failed") from exc


@router.get("/jobs", response_model=list[JobPosting])
def list_jobs() -> list[JobPosting]:
    return job_catalog.list_active()


@router.post("/jobs/gmail/microsoft-alerts/today", response_model=JobAlertIngestionResult)
def ingest_today_microsoft_careers_alert() -> JobAlertIngestionResult:
    """Read, parse, and shortlist today's alert. This endpoint cannot apply to jobs."""
    try:
        alerts = gmail_service.microsoft_careers_alerts(datetime.now(UTC).date())
    except PermissionError as exc:
        raise HTTPException(409, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Gmail job-alert read failed") from exc
    if not alerts:
        raise HTTPException(404, "No Microsoft Careers job alert found for today")
    alert = max(alerts, key=lambda item: item["received_at"])
    try:
        postings, reported_count = MicrosoftCareersAlertParser().parse(**alert)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not postings:
        raise HTTPException(422, "The Microsoft Careers alert contained no reviewable job cards")
    return job_catalog.ingest_alert(postings, reported_count, alert["message_url"])


@router.post("/jobs/match", response_model=JobMatch)
def match_job(payload: JobMatchBody) -> JobMatch:
    return JobMatchingService().score(payload.job, payload.candidate)


@router.post("/resume/claims", response_model=ResumeClaim, status_code=201)
def register_resume_claim(payload: ResumeClaimCreate) -> ResumeClaim:
    try:
        return resume_service.register_claim(
            get_settings().local_user_id, payload, knowledge_service.facts
        )
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/resume/claims", response_model=list[ResumeClaim])
def list_resume_claims() -> list[ResumeClaim]:
    user_id = get_settings().local_user_id
    return [item for item in resume_service.claims.values() if item.user_id == user_id]


@router.post("/resume/tailor", response_model=ResumeTailoringResult)
def tailor_resume(payload: ResumeTailoringRequest) -> ResumeTailoringResult:
    try:
        return resume_service.tailor(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/applications/drafts", response_model=ApplicationDraft, status_code=201)
def create_application_draft(payload: ApplicationDraftCreate) -> ApplicationDraft:
    try:
        return application_service.create_draft(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/applications/drafts", response_model=list[ApplicationDraft])
def list_application_drafts() -> list[ApplicationDraft]:
    user_id = get_settings().local_user_id
    return [item for item in application_service.drafts.values() if item.user_id == user_id]


@router.get("/applications/{application_id}/review", response_model=ApplicationReview)
def review_application(application_id: UUID) -> ApplicationReview:
    try:
        return application_service.review(get_settings().local_user_id, application_id)
    except KeyError as exc:
        raise HTTPException(404, "Application not found") from exc


@router.post("/applications/{application_id}/submission-preview", response_model=ExecutionPreview)
def preview_application_submission(application_id: UUID) -> ExecutionPreview:
    try:
        action = application_service.submission_action(
            get_settings().local_user_id, application_id
        )
    except KeyError as exc:
        raise HTTPException(404, "Application not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    approval = store.create_action(action)
    decision = policy.evaluate(action)
    return ExecutionPreview(
        action=action,
        approval=approval,
        allowed=decision.allowed,
        reason=decision.reason,
    )


@router.post("/email/threads", response_model=EmailThread, status_code=201)
def ingest_email_thread(payload: EmailThread) -> EmailThread:
    if payload.user_id != get_settings().local_user_id:
        raise HTTPException(403, "Email thread belongs to another user")
    try:
        return email_service.ingest_thread(payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/email/threads", response_model=list[EmailThread])
def list_email_threads() -> list[EmailThread]:
    user_id = get_settings().local_user_id
    return [item for (owner, _), item in email_service.threads.items() if owner == user_id]

@router.get("/email/drafts", response_model=list[EmailReplyDraft])
def list_email_drafts() -> list[EmailReplyDraft]:
    return [draft for draft in email_service.drafts.values() if draft.user_id == get_settings().local_user_id]


@router.get("/email/threads/{thread_id}/signals", response_model=list[EmailSignal])
def email_signals(thread_id: str) -> list[EmailSignal]:
    try:
        return email_service.signals(get_settings().local_user_id, thread_id)
    except KeyError as exc:
        raise HTTPException(404, "Email thread not found") from exc


@router.post("/email/threads/{thread_id}/reply-drafts", response_model=EmailReplyDraft)
def create_email_reply(thread_id: str, payload: EmailReplyBody) -> EmailReplyDraft:
    try:
        return email_service.create_reply_draft(
            get_settings().local_user_id, thread_id, payload.body
        )
    except KeyError as exc:
        raise HTTPException(404, "Email thread not found") from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

@router.post("/email/drafts", response_model=EmailReplyDraft, status_code=201)
def create_new_email_draft(payload: NewEmailDraftBody) -> EmailReplyDraft:
    try:
        return email_service.create_new_draft(get_settings().local_user_id, payload.recipients, payload.subject, payload.body)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/email/drafts/{draft_id}/send-preview", response_model=ExecutionPreview)
def preview_email_send(draft_id: UUID) -> ExecutionPreview:
    try:
        action = email_service.send_action(get_settings().local_user_id, draft_id)
    except KeyError as exc:
        raise HTTPException(404, "Email draft not found") from exc
    approval = store.create_action(action)
    decision = policy.evaluate(action)
    return ExecutionPreview(
        action=action, approval=approval, allowed=decision.allowed, reason=decision.reason
    )


@router.post("/email/drafts/{draft_id}/send/{approval_id}")
def send_gmail_draft(draft_id: UUID, approval_id: UUID) -> dict[str, str]:
    try:
        draft = email_service.drafts[draft_id]
        approval = store.approvals[approval_id]
        action = store.actions[approval.action_id]
    except KeyError as exc:
        raise HTTPException(404, "Email draft or approval not found") from exc
    if approval.status != ApprovalStatus.APPROVED_ONCE:
        raise HTTPException(403, "Email sending requires approve-once authorization")
    if action.action != "send_email" or action.idempotency_key != f"email-send:{draft.id}":
        raise HTTPException(409, "Approval does not authorize this email draft")
    try:
        evidence = gmail_service.send_message(draft.recipients, draft.subject, draft.body, draft.thread_id)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except httpx.HTTPError as exc:
        logger.warning("Gmail send failed: %s", str(exc))
        raise HTTPException(502, "Gmail send failed") from exc
    return {**evidence, "status": "sent", "recipient": ", ".join(draft.recipients)}


@router.post("/calendar/events/proposals", response_model=CalendarEvent, status_code=201)
def propose_calendar_event(payload: CalendarEventCreate) -> CalendarEvent:
    try:
        return calendar_service.propose(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/calendar/events", response_model=list[CalendarEvent])
def list_calendar_events() -> list[CalendarEvent]:
    user_id = get_settings().local_user_id
    return [item for item in calendar_service.events.values() if item.user_id == user_id]


@router.post("/calendar/events/{event_id}/create-preview", response_model=ExecutionPreview)
def preview_calendar_create(event_id: UUID) -> ExecutionPreview:
    try:
        action = calendar_service.create_action(get_settings().local_user_id, event_id)
    except KeyError as exc:
        raise HTTPException(404, "Calendar event not found") from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    approval = store.create_action(action)
    decision = policy.evaluate(action)
    return ExecutionPreview(
        action=action, approval=approval, allowed=decision.allowed, reason=decision.reason
    )


@router.post("/content/drafts", response_model=ContentDraft, status_code=201)
def create_content_draft(payload: ContentDraftCreate) -> ContentDraft:
    try:
        return content_service.create_draft(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/content/drafts", response_model=list[ContentDraft])
def list_content_drafts() -> list[ContentDraft]:
    user_id = get_settings().local_user_id
    return [item for item in content_service.drafts.values() if item.user_id == user_id]


@router.post("/content/drafts/{draft_id}/publish-preview", response_model=ExecutionPreview)
def preview_content_publish(draft_id: UUID) -> ExecutionPreview:
    try:
        action = content_service.publishing_action(get_settings().local_user_id, draft_id)
    except KeyError as exc:
        raise HTTPException(404, "Content draft not found") from exc
    approval = store.create_action(action)
    decision = policy.evaluate(action)
    return ExecutionPreview(
        action=action, approval=approval, allowed=decision.allowed, reason=decision.reason
    )


@router.post("/media/routes/preview", response_model=MediaRoute)
def preview_media_route(payload: MediaGenerationRequest) -> MediaRoute:
    return media_router.route(payload)


@router.post("/video/projects", response_model=VideoProject, status_code=201)
def create_video_project(payload: VideoProjectCreate) -> VideoProject:
    try:
        return video_service.create_project(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/content/linkedin/compose", response_model=ContentDraft, status_code=201)
def compose_linkedin_draft(payload: LinkedInComposeBody) -> ContentDraft:
    try:
        return content_service.compose_linkedin_draft(
            get_settings().local_user_id,
            topic=payload.topic,
            audience=payload.audience,
            key_points=payload.key_points,
            call_to_action=payload.call_to_action,
            target_account=payload.target_account,
            tone=payload.tone,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/oauth/linkedin/status")
def linkedin_oauth_status() -> dict[str, bool | str]:
    return {
        "configured": linkedin_oauth.configured,
        "connected": linkedin_oauth.connected,
        "redirect_uri": linkedin_oauth.redirect_uri,
    }


@router.post("/oauth/linkedin/configure")
def configure_linkedin_oauth(payload: LinkedInConfigurationBody) -> dict[str, bool | str]:
    try:
        linkedin_oauth.configure(
            payload.client_id,
            payload.client_secret,
            payload.redirect_uri,
            payload.author_urn,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        linkedin_keychain.store(LINKEDIN_CREDENTIAL_ID, payload.client_secret)
        LINKEDIN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LINKEDIN_CONFIG_PATH.write_text(json.dumps({
            "client_id": payload.client_id,
            "redirect_uri": payload.redirect_uri,
            "author_urn": payload.author_urn,
        }))
    except (OSError, RuntimeError) as exc:
        raise HTTPException(500, "Could not save LinkedIn credentials securely") from exc
    store.append_audit(
        AuditEvent(
            event_type="linkedin.oauth.configured",
            actor="local-user",
            target_type="oauth_provider",
            target_id="linkedin",
            safe_payload={"redirect_uri": payload.redirect_uri, "secret_stored": True},
        )
    )
    return {"configured": True, "connected": False, "redirect_uri": linkedin_oauth.redirect_uri}


@router.get("/oauth/linkedin/start")
def start_linkedin_oauth() -> RedirectResponse:
    try:
        return RedirectResponse(linkedin_oauth.authorization_url())
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.get("/oauth/linkedin/callback", response_class=PlainTextResponse)
def linkedin_oauth_callback(code: str, state: str) -> str:
    try:
        linkedin_oauth.exchange_code(code, state)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except (RuntimeError, httpx.HTTPError, KeyError) as exc:
        logger.warning("LinkedIn OAuth exchange failed")
        raise HTTPException(502, "LinkedIn authorization failed") from exc
    return "LinkedIn connected to Friday. You may close this window."


@router.post("/content/drafts/{draft_id}/publish/{approval_id}", response_model=PublicationEvidence)
def publish_linkedin_draft(draft_id: UUID, approval_id: UUID) -> PublicationEvidence:
    try:
        draft = content_service.drafts[draft_id]
        approval = store.approvals[approval_id]
        action = store.actions[approval.action_id]
    except KeyError as exc:
        raise HTTPException(404, "Draft or publishing approval not found") from exc
    if approval.status != ApprovalStatus.APPROVED_ONCE:
        raise HTTPException(403, "Publishing requires approve-once authorization")
    if action.action != "publish_content" or action.idempotency_key != f"publish:{draft.platform}:{draft.id}":
        raise HTTPException(409, "Approval does not authorize this draft")
    author_urn = linkedin_oauth.author_urn or get_settings().linkedin_author_urn
    if not author_urn:
        raise HTTPException(409, "LinkedIn member URN is not configured")
    try:
        post_id = linkedin_oauth.publish_text(author_urn, draft.body)
    except PermissionError as exc:
        raise HTTPException(401, str(exc)) from exc
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        logger.warning("LinkedIn publish failed")
        raise HTTPException(502, "LinkedIn publishing failed") from exc
    draft.status = "published"
    return PublicationEvidence(
        platform=draft.platform,
        post_id=post_id,
        public_url=f"https://www.linkedin.com/feed/update/{post_id}",
        status="published",
    )


@router.get("/video/projects", response_model=list[VideoProject])
def list_video_projects() -> list[VideoProject]:
    user_id = get_settings().local_user_id
    return [item for item in video_service.projects.values() if item.user_id == user_id]


@router.post("/video/projects/{project_id}/render-local", response_model=VideoRenderEvidence)
def render_video_project_locally(project_id: UUID) -> VideoRenderEvidence:
    try:
        project = video_service.projects[project_id]
    except KeyError as exc:
        raise HTTPException(404, "Video project not found") from exc
    try:
        evidence = local_video_renderer.render(project)
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        logger.exception("Local video render failed for project %s", project_id)
        raise HTTPException(500, "Local video render failed") from exc
    verification = video_service.verify_render(evidence)
    if not verification.verified:
        raise HTTPException(500, f"Rendered video failed QA: {verification.missing_evidence}")
    return evidence


@router.post("/learning/concepts", response_model=LearningConcept, status_code=201)
def create_learning_concept(payload: LearningConceptBody) -> LearningConcept:
    try:
        return learning_service.create_concept(get_settings().local_user_id, payload.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/learning/concepts", response_model=list[LearningConcept])
def list_learning_concepts() -> list[LearningConcept]:
    user_id = get_settings().local_user_id
    return [item for item in learning_service.concepts.values() if item.user_id == user_id]


@router.post("/learning/sessions", response_model=StudySession, status_code=201)
def create_study_session(payload: StudySessionCreate) -> StudySession:
    try:
        return learning_service.plan_session(get_settings().local_user_id, payload)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/learning/sessions", response_model=list[StudySession])
def list_study_sessions() -> list[StudySession]:
    user_id = get_settings().local_user_id
    return [item for item in learning_service.sessions.values() if item.user_id == user_id]
