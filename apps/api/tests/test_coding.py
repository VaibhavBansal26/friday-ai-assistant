from pathlib import Path

import pytest

from friday.domain.models import CommandRisk
from friday.services.coding import CodingSafetyService


class FakeRunner:
    def __init__(self, result=(0, "ok", "")):
        self.result = result
        self.calls = []

    def run(self, command, cwd):
        self.calls.append((command, cwd))
        return self.result


def test_path_escape_is_denied(tmp_path: Path):
    with pytest.raises(PermissionError, match="outside"):
        CodingSafetyService(tmp_path).resolve_path("../secret")


@pytest.mark.parametrize(
    "command",
    [
        ["git", "reset", "--hard"],
        ["git", "clean", "-fd"],
        ["git", "push", "--force"],
        ["rm", "-rf", "build"],
    ],
)
def test_destructive_commands_are_denied(command, tmp_path: Path):
    assessment = CodingSafetyService(tmp_path).assess(command)
    assert assessment.risk == CommandRisk.DESTRUCTIVE
    assert not assessment.allowed
    assert assessment.requires_approval


def test_push_and_pr_creation_are_external_writes(tmp_path: Path):
    service = CodingSafetyService(tmp_path)
    for command in (["git", "push"], ["gh", "pr", "create"]):
        assessment = service.assess(list(command))
        assert assessment.risk == CommandRisk.EXTERNAL_WRITE
        assert not assessment.allowed


def test_failed_test_command_is_not_claimed_successful(tmp_path: Path):
    runner = FakeRunner((1, "1 failed", "failure"))
    evidence = CodingSafetyService(tmp_path, runner).run(["pytest"], ".")
    assert evidence.exit_code == 1
    assert not evidence.verified_success


def test_command_output_is_redacted(tmp_path: Path):
    runner = FakeRunner((0, "token sk-project_abcdefghijklmnopqrstuvwxyz", ""))
    evidence = CodingSafetyService(tmp_path, runner).run(["git", "status"], ".")
    assert "sk-project" not in evidence.stdout
    assert "[REDACTED]" in evidence.stdout
