from uuid import uuid4

import pytest

from friday.services.macos_keychain import KEYCHAIN_SERVICE, MacOSKeychain


class FakeRunner:
    def __init__(self, return_code: int = 0) -> None:
        self.return_code = return_code
        self.calls: list[tuple[list[str], str | None]] = []

    def run(self, args: list[str], *, secret_stdin: str | None = None) -> int:
        self.calls.append((args, secret_stdin))
        return self.return_code


def test_secret_is_never_placed_in_command_arguments():
    runner = FakeRunner()
    credential_id = uuid4()
    MacOSKeychain(runner).store(credential_id, "highly-sensitive-value")
    args, secret_stdin = runner.calls[0]
    assert "highly-sensitive-value" not in args
    assert secret_stdin == "highly-sensitive-value"
    assert KEYCHAIN_SERVICE in args
    assert str(credential_id) in args


def test_empty_secret_is_rejected_before_keychain_call():
    runner = FakeRunner()
    with pytest.raises(ValueError, match="empty"):
        MacOSKeychain(runner).store(uuid4(), "")
    assert runner.calls == []


def test_exists_returns_only_boolean_status():
    assert MacOSKeychain(FakeRunner(0)).exists(uuid4())
    assert not MacOSKeychain(FakeRunner(44)).exists(uuid4())


def test_write_failure_contains_no_secret():
    with pytest.raises(RuntimeError, match="Keychain write failed") as error:
        MacOSKeychain(FakeRunner(1)).store(uuid4(), "do-not-leak")
    assert "do-not-leak" not in str(error.value)


def test_delete_is_idempotent_for_missing_item():
    MacOSKeychain(FakeRunner(44)).delete(uuid4())


def test_unexpected_delete_failure_is_reported_safely():
    with pytest.raises(RuntimeError, match="Keychain deletion failed"):
        MacOSKeychain(FakeRunner(1)).delete(uuid4())

