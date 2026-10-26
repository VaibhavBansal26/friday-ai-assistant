import re
import subprocess
from pathlib import Path

from friday.domain.models import (
    GitOperationEvidence,
    PullRequestFinding,
    VerificationResult,
)


COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
PR_URL_PATTERN = re.compile(r"^https://github\.com/[^/]+/[^/]+/pull/(\d+)$")


class GitHubVerificationService:
    def __init__(self) -> None:
        self.comment_keys: set[str] = set()

    def verify(self, evidence: GitOperationEvidence) -> VerificationResult:
        missing: list[str] = []
        if evidence.operation == "commit":
            if not evidence.local_commit or not COMMIT_PATTERN.fullmatch(evidence.local_commit):
                missing.append("valid 40-character commit hash")
        elif evidence.operation == "push":
            if not evidence.local_commit or not COMMIT_PATTERN.fullmatch(evidence.local_commit):
                missing.append("valid local commit hash")
            if not evidence.remote_commit or evidence.remote_commit != evidence.local_commit:
                missing.append("matching remote branch commit")
        elif evidence.operation == "create_pull_request":
            match = (
                PR_URL_PATTERN.fullmatch(evidence.pull_request_url)
                if evidence.pull_request_url
                else None
            )
            if not evidence.pull_request_number:
                missing.append("pull request number")
            if not match:
                missing.append("valid GitHub pull request URL")
            elif evidence.pull_request_number != int(match.group(1)):
                missing.append("matching pull request number and URL")
        elif evidence.operation == "comment":
            if not evidence.provider_comment_id:
                missing.append("provider comment ID")
        elif evidence.operation == "merge":
            if evidence.provider_state != "merged":
                missing.append("provider merged state")
            if not evidence.remote_commit or not COMMIT_PATTERN.fullmatch(evidence.remote_commit):
                missing.append("merge commit hash")
        else:
            missing.append("known Git operation")
        return VerificationResult(
            verified=not missing,
            outcome="completed" if not missing else "unverified",
            missing_evidence=missing,
        )

    def register_comment(self, repository: str, pull_number: int, body_hash: str) -> None:
        key = f"{repository}:{pull_number}:{body_hash}"
        if key in self.comment_keys:
            raise ValueError("Duplicate pull request comment is blocked")
        self.comment_keys.add(key)


class ReviewFindingValidator:
    def validate(self, finding: PullRequestFinding) -> None:
        if finding.line is None and not finding.region:
            raise ValueError("Review finding requires a line or region")
        if finding.confidence not in {"high", "medium"}:
            raise ValueError("Low-confidence review findings must be omitted")
        fields = [
            finding.problem,
            finding.why_it_matters,
            finding.failure_scenario,
            finding.suggested_fix,
        ]
        if any(len(value.strip()) < 8 for value in fields):
            raise ValueError("Review finding lacks actionable detail")


class GitExecutionService:
    """Perform an explicitly approved local commit and return verifiable evidence."""

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def _relative_path(self, value: str) -> str:
        candidate = (self.workspace_root / value).resolve()
        if candidate != self.workspace_root and self.workspace_root not in candidate.parents:
            raise PermissionError("Commit path is outside the authorized workspace")
        relative = str(candidate.relative_to(self.workspace_root))
        if relative.startswith(".git/") or relative == ".git":
            raise PermissionError("Git internals cannot be staged directly")
        return relative

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command,
            cwd=self.workspace_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def commit(self, message: str, paths: list[str]) -> GitOperationEvidence:
        clean_message = message.strip()
        if not clean_message or len(clean_message) > 200:
            raise ValueError("Commit message must contain 1-200 characters")
        if not paths:
            raise ValueError("At least one explicit path is required")
        relative_paths = [self._relative_path(path) for path in paths]
        staged = self._run(["git", "add", "--", *relative_paths])
        if staged.returncode != 0:
            raise RuntimeError("Git staging failed")
        diff = self._run(["git", "diff", "--cached", "--quiet", "--", *relative_paths])
        if diff.returncode == 0:
            raise ValueError("Selected paths contain no staged changes")
        if diff.returncode != 1:
            raise RuntimeError("Unable to inspect staged Git changes")
        committed = self._run(["git", "commit", "-m", clean_message, "--", *relative_paths])
        if committed.returncode != 0:
            raise RuntimeError("Git commit failed")
        revision = self._run(["git", "rev-parse", "HEAD"])
        commit_hash = revision.stdout.strip()
        evidence = GitOperationEvidence(operation="commit", local_commit=commit_hash)
        if not GitHubVerificationService().verify(evidence).verified:
            raise RuntimeError("Commit evidence could not be verified")
        return evidence
