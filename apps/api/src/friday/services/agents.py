from dataclasses import dataclass
import re

from friday.domain.models import RiskLevel


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    purpose: str
    tool_groups: frozenset[str]
    maximum_risk: RiskLevel
    can_delegate: bool = False


AGENTS = (
    AgentDefinition("supervisor", "Route and coordinate verified work", frozenset(), RiskLevel.READ_ONLY, True),
    AgentDefinition("voice", "Validate voice turns and render approved responses", frozenset({"voice"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("intent-classification", "Classify user intent", frozenset(), RiskLevel.READ_ONLY),
    AgentDefinition("risk-classification", "Classify action risk", frozenset(), RiskLevel.READ_ONLY),
    AgentDefinition("task-manager", "Manage local tasks", frozenset({"tasks"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("idea-partner", "Structure and challenge ideas", frozenset({"ideas"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("research", "Retrieve cited public research", frozenset({"research", "browser-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("personal-memory", "Propose governed memories", frozenset({"memory"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("knowledge-retrieval", "Retrieve cited local knowledge", frozenset({"knowledge-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("job-discovery", "Read and normalize job sources", frozenset({"jobs-read", "browser-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("job-matching", "Score jobs against verified facts", frozenset({"jobs-read", "facts-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("company-research", "Research companies with citations", frozenset({"research", "browser-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("resume-tailoring", "Tailor source-backed resumes", frozenset({"resume", "facts-read"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("job-application", "Prepare and submit approved applications", frozenset({"applications", "browser-form"}), RiskLevel.HIGH_IMPACT),
    AgentDefinition("email-summary", "Read and summarize email", frozenset({"email-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("email-reply", "Draft and send approved replies", frozenset({"email-read", "email-write"}), RiskLevel.EXTERNAL_COMMUNICATION),
    AgentDefinition("calendar", "Read and change approved calendar events", frozenset({"calendar-read", "calendar-write"}), RiskLevel.EXTERNAL_COMMUNICATION),
    AgentDefinition("coding", "Modify scoped local repositories", frozenset({"repository-read", "repository-write", "shell-safe"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("code-review", "Review source and diffs", frozenset({"repository-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("github", "Perform approved GitHub operations", frozenset({"repository-read", "github-write"}), RiskLevel.HIGH_IMPACT),
    AgentDefinition("ci-debugging", "Read CI and prepare fixes", frozenset({"repository-read", "ci-read", "repository-write"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("website-builder", "Build and verify local websites", frozenset({"repository-write", "shell-safe", "browser-local"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("design", "Create design specifications", frozenset({"design"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("design-qa", "Audit accessibility and visual output", frozenset({"browser-local", "design-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("content-strategy", "Plan sourced content", frozenset({"research", "content"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("medium", "Adapt drafts for Medium", frozenset({"content"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("linkedin", "Adapt drafts for LinkedIn", frozenset({"content"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("x", "Adapt drafts for X", frozenset({"content"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("instagram", "Adapt drafts for Instagram", frozenset({"content", "media"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("youtube", "Adapt drafts for YouTube", frozenset({"content", "media"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("video-production", "Render and QA local videos", frozenset({"media", "video-render"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("publishing", "Publish approved content", frozenset({"publishing-write"}), RiskLevel.EXTERNAL_COMMUNICATION),
    AgentDefinition("learning", "Teach through active recall", frozenset({"learning", "knowledge-read"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("mock-interviewer", "Run and evaluate interviews", frozenset({"learning", "voice"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("study-planner", "Create adaptive study plans", frozenset({"learning", "tasks"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("verification", "Verify evidence for claimed outcomes", frozenset({"evidence-read"}), RiskLevel.READ_ONLY),
    AgentDefinition("security-policy", "Enforce deterministic policy", frozenset(), RiskLevel.READ_ONLY),
    AgentDefinition("notification", "Create local notifications", frozenset({"notifications"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("spotify", "Search and control Spotify playback", frozenset({"spotify", "device"}), RiskLevel.LOCAL_REVERSIBLE),
    AgentDefinition("browser-use", "Navigate and read approved web domains", frozenset({"browser-read", "browser-form"}), RiskLevel.HIGH_IMPACT),
)

AGENT_REGISTRY = {agent.name: agent for agent in AGENTS}


@dataclass(frozen=True)
class AgentRoute:
    agent: str
    intent: str
    tool_group: str
    risk: RiskLevel
    confidence: float


ROUTING_RULES: tuple[tuple[str, str, str, RiskLevel, tuple[str, ...]], ...] = (
    ("linkedin", "linkedin_content", "content", RiskLevel.LOCAL_REVERSIBLE, (r"linkedin",)),
    ("medium", "medium_content", "content", RiskLevel.LOCAL_REVERSIBLE, (r"\bmedium\b", r"medium article")),
    ("x", "x_content", "content", RiskLevel.LOCAL_REVERSIBLE, (r"\btwitter\b", r"\bx post\b", r"\btweet", r"x thread")),
    ("youtube", "youtube_content", "media", RiskLevel.LOCAL_REVERSIBLE, (r"youtube shorts?", r"youtube video", r"\bshorts? video")),
    ("video-production", "video_production", "video-render", RiskLevel.LOCAL_REVERSIBLE, (r"render.*video", r"create.*video", r"make.*video")),
    ("learning", "learning_plan", "learning", RiskLevel.LOCAL_REVERSIBLE, (r"learning plan", r"study plan", r"teach me", r"learn\b")),
    ("github", "clone_repository", "github-write", RiskLevel.HIGH_IMPACT, (r"clone.*repo", r"clone.*github")),
    ("github", "publish_repository_change", "github-write", RiskLevel.HIGH_IMPACT, (r"push.*repo", r"create.*pull request", r"open.*pull request")),
    ("coding", "commit_code", "repository-write", RiskLevel.LOCAL_REVERSIBLE, (r"commit.*code", r"commit.*changes", r"git commit")),
    ("code-review", "analyze_code", "repository-read", RiskLevel.READ_ONLY, (r"analy[sz]e.*code", r"review.*code", r"inspect.*repo", r"code.*folder")),
    ("job-application", "job_application", "applications", RiskLevel.HIGH_IMPACT, (r"apply.*job", r"submit.*application")),
    ("job-discovery", "job_discovery", "jobs-read", RiskLevel.READ_ONLY, (r"find.*jobs?", r"search.*jobs?")),
    ("email-reply", "email_reply", "email-write", RiskLevel.EXTERNAL_COMMUNICATION, (r"send.*email", r"reply.*email")),
    ("calendar", "calendar_change", "calendar-write", RiskLevel.EXTERNAL_COMMUNICATION, (r"schedule.*meeting", r"create.*calendar", r"add.*calendar")),
    ("website-builder", "website_build", "repository-write", RiskLevel.LOCAL_REVERSIBLE, (r"build.*website", r"create.*website", r"landing page")),
    ("research", "research", "research", RiskLevel.READ_ONLY, (r"research", r"look up", r"investigate")),
    ("task-manager", "task_management", "tasks", RiskLevel.LOCAL_REVERSIBLE, (r"create.*task", r"add.*task", r"plan my day")),
    ("spotify", "spotify_control", "spotify", RiskLevel.LOCAL_REVERSIBLE, (r"spotify", r"play.*music", r"play.*playlist")),
    ("browser-use", "browser_navigation", "browser-read", RiskLevel.READ_ONLY, (r"open.*browser", r"browse.*site", r"read.*webpage", r"go to.*website")),
)


def route_request(request: str) -> AgentRoute:
    normalized = " ".join(request.lower().split())
    for agent, intent, tool_group, risk, patterns in ROUTING_RULES:
        if any(re.search(pattern, normalized) for pattern in patterns):
            if agent not in AGENT_REGISTRY:
                raise RuntimeError(f"Capability route references unknown agent '{agent}'")
            validate_delegation(agent, tool_group, risk)
            return AgentRoute(agent, intent, tool_group, risk, 0.95)
    return AgentRoute("idea-partner", "general_assistance", "ideas", RiskLevel.LOCAL_REVERSIBLE, 0.35)


def validate_delegation(agent_name: str, tool_group: str, requested_risk: RiskLevel) -> None:
    agent = AGENT_REGISTRY[agent_name]
    if tool_group not in agent.tool_groups:
        raise PermissionError(f"Agent '{agent_name}' cannot access tool group '{tool_group}'")
    if requested_risk > agent.maximum_risk:
        raise PermissionError(f"Agent '{agent_name}' exceeds its maximum risk level")
