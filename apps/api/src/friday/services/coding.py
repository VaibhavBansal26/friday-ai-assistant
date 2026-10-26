from __future__ import annotations

import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from friday.core.redaction import redact
from friday.domain.models import (
    CommandAssessment,
    CommandEvidence,
    CommandRisk,
    RepositoryContext,
)


DESTRUCTIVE_PREFIXES = {
    ("git", "reset", "--hard"),
    ("git", "clean", "-fd"),
    ("git", "push", "--force"),
    ("git", "push", "-f"),
    ("git", "branch", "-D"),
    ("rm", "-rf"),
}
EXTERNAL_WRITE_PREFIXES = {
    ("git", "push"),
    ("gh", "pr", "create"),
    ("gh", "pr", "merge"),
    ("gh", "pr", "comment"),
}
LOCAL_WRITE_COMMANDS = {"ruff", "prettier", "eslint", "pytest", "npm", "cargo"}


class ProcessRunner(Protocol):
    def run(self, command: list[str], cwd: Path) -> tuple[int, str, str]: ...


class SafeProcessRunner:
    def run(self, command: list[str], cwd: Path) -> tuple[int, str, str]:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            timeout=300,
            env={"PATH": os.environ.get("PATH", "")},
        )
        return completed.returncode, completed.stdout, completed.stderr


class CodingSafetyService:
    def __init__(self, workspace_root: Path, runner: ProcessRunner | None = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.runner = runner or SafeProcessRunner()

    def resolve_path(self, value: str | Path) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = self.workspace_root / candidate
        resolved = candidate.resolve()
        if resolved != self.workspace_root and self.workspace_root not in resolved.parents:
            raise PermissionError("Path is outside the authorized workspace")
        return resolved

    def assess(self, command: list[str]) -> CommandAssessment:
        if not command:
            raise ValueError("Command cannot be empty")
        normalized = tuple(command)
        if any(normalized[: len(prefix)] == prefix for prefix in DESTRUCTIVE_PREFIXES):
            return CommandAssessment(
                command=command,
                risk=CommandRisk.DESTRUCTIVE,
                allowed=False,
                requires_approval=True,
                reason="Destructive commands require strong explicit approval",
            )
        if any(normalized[: len(prefix)] == prefix for prefix in EXTERNAL_WRITE_PREFIXES):
            return CommandAssessment(
                command=command,
                risk=CommandRisk.EXTERNAL_WRITE,
                allowed=False,
                requires_approval=True,
                reason="External repository writes require explicit approval",
            )
        risk = CommandRisk.LOCAL_WRITE if command[0] in LOCAL_WRITE_COMMANDS else CommandRisk.READ_ONLY
        return CommandAssessment(
            command=command,
            risk=risk,
            allowed=True,
            requires_approval=False,
            reason="Command is confined to the authorized workspace",
        )

    def run(self, command: list[str], cwd: str | Path = ".") -> CommandEvidence:
        assessment = self.assess(command)
        if not assessment.allowed:
            raise PermissionError(assessment.reason)
        resolved_cwd = self.resolve_path(cwd)
        started = datetime.now(UTC)
        exit_code, stdout, stderr = self.runner.run(command, resolved_cwd)
        finished = datetime.now(UTC)
        return CommandEvidence(
            command=command,
            exit_code=exit_code,
            stdout=redact(stdout),
            stderr=redact(stderr),
            started_at=started,
            finished_at=finished,
            verified_success=exit_code == 0,
        )

    def inspect_repository(self, root: str | Path = ".") -> RepositoryContext:
        resolved = self.resolve_path(root)
        status = self.run(["git", "status", "--short", "--branch"], resolved)
        if not status.verified_success:
            raise RuntimeError("Repository inspection failed")
        lines = status.stdout.splitlines()
        branch = lines[0].removeprefix("## ").split("...")[0] if lines else None
        changed = [line[3:] for line in lines[1:] if len(line) > 3]
        instructions = [
            str(path.relative_to(resolved))
            for path in resolved.rglob("AGENTS.md")
            if ".git" not in path.parts
        ]
        return RepositoryContext(
            root=str(resolved),
            branch=branch,
            dirty=bool(changed),
            changed_files=changed,
            instruction_files=sorted(instructions),
        )
