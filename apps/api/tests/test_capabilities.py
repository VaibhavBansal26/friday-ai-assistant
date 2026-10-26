from pathlib import Path

from friday.services.capabilities import CapabilityCatalog


def test_linkedin_route_reports_missing_connection(tmp_path: Path):
    result = CapabilityCatalog(tmp_path, linkedin_connected=False).inspect("Create a LinkedIn post")
    assert result["route"]["agent"] == "linkedin"
    assert not result["readiness"]["ready"]
    assert result["readiness"]["reason"] == "Connect LinkedIn"


def test_repository_route_requires_git_context(tmp_path: Path):
    result = CapabilityCatalog(tmp_path).inspect("Analyze the code in this folder")
    assert result["route"]["agent"] == "code-review"
    assert not result["readiness"]["ready"]
    (tmp_path / ".git").mkdir()
    ready = CapabilityCatalog(tmp_path).inspect("Analyze the code in this folder")
    assert ready["readiness"]["ready"]


def test_github_write_is_marked_for_approval(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    result = CapabilityCatalog(tmp_path).inspect("Clone a repo from my GitHub")
    assert result["readiness"]["approval_required"]
