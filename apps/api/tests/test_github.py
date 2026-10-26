import pytest

from friday.domain.models import GitOperationEvidence, PullRequestFinding, ReviewSeverity
from friday.services.github import GitExecutionService, GitHubVerificationService, ReviewFindingValidator


HASH = "a" * 40


def test_commit_requires_real_hash_shape():
    result = GitHubVerificationService().verify(
        GitOperationEvidence(operation="commit", local_commit="looks-valid")
    )
    assert not result.verified
    assert "valid 40-character commit hash" in result.missing_evidence


def test_push_requires_remote_ref_to_match_local_commit():
    result = GitHubVerificationService().verify(
        GitOperationEvidence(operation="push", local_commit=HASH, remote_commit="b" * 40)
    )
    assert not result.verified
    assert "matching remote branch commit" in result.missing_evidence


def test_pull_request_requires_matching_number_and_url():
    result = GitHubVerificationService().verify(
        GitOperationEvidence(
            operation="create_pull_request",
            pull_request_number=42,
            pull_request_url="https://github.com/acme/repo/pull/41",
        )
    )
    assert not result.verified
    assert "matching pull request number and URL" in result.missing_evidence


def test_valid_pull_request_evidence_is_verified():
    result = GitHubVerificationService().verify(
        GitOperationEvidence(
            operation="create_pull_request",
            pull_request_number=42,
            pull_request_url="https://github.com/acme/repo/pull/42",
        )
    )
    assert result.verified


def test_duplicate_pr_comment_is_blocked():
    service = GitHubVerificationService()
    service.register_comment("acme/repo", 42, "body-hash")
    with pytest.raises(ValueError, match="Duplicate"):
        service.register_comment("acme/repo", 42, "body-hash")


def test_low_confidence_review_noise_is_rejected():
    finding = PullRequestFinding(
        severity=ReviewSeverity.LOW,
        confidence="low",
        file="app.py",
        line=10,
        problem="Potential issue",
        why_it_matters="Could fail under load",
        failure_scenario="Concurrent calls overlap",
        suggested_fix="Protect state with a lock",
    )
    with pytest.raises(ValueError, match="Low-confidence"):
        ReviewFindingValidator().validate(finding)


def test_review_finding_requires_location():
    finding = PullRequestFinding(
        severity=ReviewSeverity.HIGH,
        confidence="high",
        file="app.py",
        problem="Race condition",
        why_it_matters="Requests can corrupt state",
        failure_scenario="Two concurrent requests write together",
        suggested_fix="Use a transaction boundary",
    )
    with pytest.raises(ValueError, match="line or region"):
        ReviewFindingValidator().validate(finding)


def test_git_execution_creates_verified_commit(tmp_path):
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Friday Test"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "friday@example.test"], cwd=tmp_path, check=True
    )
    (tmp_path / "result.txt").write_text("verified", encoding="utf-8")
    evidence = GitExecutionService(tmp_path).commit("Verify execution", ["result.txt"])
    assert GitHubVerificationService().verify(evidence).verified
    assert len(evidence.local_commit or "") == 40


def test_git_execution_rejects_path_escape(tmp_path):
    with pytest.raises(PermissionError, match="outside"):
        GitExecutionService(tmp_path).commit("Unsafe", ["../outside.txt"])
