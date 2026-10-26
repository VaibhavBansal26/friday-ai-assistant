from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


KEYCHAIN_SERVICE = "ai.friday.desktop.credentials"


class CommandRunner(Protocol):
    def run(self, args: list[str], *, secret_stdin: str | None = None) -> int: ...


class SecurityCliRunner:
    """Runs macOS `security` without returning stdout, stderr, or secret material."""

    def run(self, args: list[str], *, secret_stdin: str | None = None) -> int:
        protected_input = None
        if secret_stdin is not None:
            # `security add-generic-password -w` prompts twice when the password is
            # supplied interactively. Feed both answers through stdin so the secret
            # never appears in argv, logs, or process listings.
            protected_input = f"{secret_stdin}\n{secret_stdin}\n"
        completed = subprocess.run(
            args,
            input=protected_input,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=10,
        )
        return completed.returncode


@dataclass(frozen=True)
class KeychainReference:
    credential_id: UUID
    service: str = KEYCHAIN_SERVICE

    @property
    def account(self) -> str:
        return str(self.credential_id)


class MacOSKeychain:
    """Trusted local adapter. Secret reads are allowed only through `use_secret`."""

    def __init__(self, runner: CommandRunner | None = None) -> None:
        self.runner = runner or SecurityCliRunner()

    def exists(self, credential_id: UUID) -> bool:
        reference = KeychainReference(credential_id)
        return (
            self.runner.run(
                [
                    "security",
                    "find-generic-password",
                    "-s",
                    reference.service,
                    "-a",
                    reference.account,
                ]
            )
            == 0
        )

    def store(self, credential_id: UUID, secret: str) -> None:
        if not secret:
            raise ValueError("Secret cannot be empty")
        reference = KeychainReference(credential_id)
        # The secret is passed as stdin to a trusted helper contract, never as a command argument.
        code = self.runner.run(
            [
                "security",
                "add-generic-password",
                "-U",
                "-s",
                reference.service,
                "-a",
                reference.account,
                "-w",
            ],
            secret_stdin=secret,
        )
        if code != 0:
            raise RuntimeError("Keychain write failed")

    def delete(self, credential_id: UUID) -> None:
        reference = KeychainReference(credential_id)
        code = self.runner.run(
            [
                "security",
                "delete-generic-password",
                "-s",
                reference.service,
                "-a",
                reference.account,
            ]
        )
        if code not in {0, 44}:
            raise RuntimeError("Keychain deletion failed")

    def load(self, credential_id: UUID) -> str:
        reference = KeychainReference(credential_id)
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", reference.service, "-a", reference.account, "-w"],
            text=True,
            capture_output=True,
            check=False,
            timeout=10,
        )
        if completed.returncode != 0:
            raise KeyError("Credential is unavailable")
        return completed.stdout.rstrip("\n")
