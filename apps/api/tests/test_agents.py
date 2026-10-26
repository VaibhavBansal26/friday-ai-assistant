import pytest

from friday.domain.models import RiskLevel
from friday.services.agents import AGENTS, AGENT_REGISTRY, route_request, validate_delegation


def test_registry_contains_unique_agents():
    assert len(AGENTS) >= 35
    assert len(AGENT_REGISTRY) == len(AGENTS)


def test_supervisor_has_no_direct_tool_access():
    assert AGENT_REGISTRY["supervisor"].tool_groups == frozenset()
    assert AGENT_REGISTRY["supervisor"].can_delegate


def test_security_and_verification_agents_are_read_only():
    assert AGENT_REGISTRY["security-policy"].maximum_risk == RiskLevel.READ_ONLY
    assert AGENT_REGISTRY["verification"].maximum_risk == RiskLevel.READ_ONLY


def test_job_discovery_cannot_submit_applications():
    with pytest.raises(PermissionError, match="cannot access"):
        validate_delegation("job-discovery", "applications", RiskLevel.HIGH_IMPACT)


def test_email_summary_cannot_send_email():
    with pytest.raises(PermissionError, match="cannot access"):
        validate_delegation("email-summary", "email-write", RiskLevel.EXTERNAL_COMMUNICATION)


def test_agent_cannot_exceed_maximum_risk_even_with_tool_group():
    with pytest.raises(PermissionError, match="maximum risk"):
        validate_delegation("coding", "repository-write", RiskLevel.HIGH_IMPACT)


def test_allowed_agent_tool_boundary_passes():
    validate_delegation("resume-tailoring", "facts-read", RiskLevel.READ_ONLY)


@pytest.mark.parametrize(("command", "agent", "intent"), [
    ("Create a post on LinkedIn", "linkedin", "linkedin_content"),
    ("Create a learning plan for machine learning", "learning", "learning_plan"),
    ("Publish a Twitter thread", "x", "x_content"),
    ("Create a YouTube Shorts video", "youtube", "youtube_content"),
    ("Analyze the code in this folder", "code-review", "analyze_code"),
    ("Commit the code changes", "coding", "commit_code"),
    ("Clone a repo from my GitHub", "github", "clone_repository"),
    ("Play my focus playlist on Spotify", "spotify", "spotify_control"),
    ("Open the browser and read this webpage", "browser-use", "browser_navigation"),
])
def test_routes_common_commands(command, agent, intent):
    route = route_request(command)
    assert route.agent == agent
    assert route.intent == intent
