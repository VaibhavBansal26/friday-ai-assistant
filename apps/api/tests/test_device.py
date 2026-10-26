from pathlib import Path

import pytest

from friday.services.device import MacOSDeviceService, ScopedFileService


class FakeRunner:
    def __init__(self, code: int = 0) -> None:
        self.code = code
        self.calls: list[list[str]] = []

    def run(self, command: list[str]) -> tuple[int, str, str]:
        self.calls.append(command)
        return self.code, "", ""


def test_device_service_opens_only_allowlisted_apps():
    runner = FakeRunner()
    service = MacOSDeviceService(runner)
    evidence = service.open_app("Music")
    assert evidence.verified
    assert runner.calls == [["open", "-a", "Music"]]
    with pytest.raises(PermissionError):
        service.open_app("Terminal")


def test_media_control_is_allowlisted_and_argument_safe():
    runner = FakeRunner()
    service = MacOSDeviceService(runner)
    assert service.media_control("Music", "play_pause").verified
    assert runner.calls[0][0:2] == ["osascript", "-e"]
    with pytest.raises(ValueError):
        service.media_control("Music", 'play_pause; do shell script "bad"')


def test_spotify_search_uses_uri_without_shell_interpolation():
    runner = FakeRunner()
    service = MacOSDeviceService(runner)
    evidence = service.spotify_search("focus mix & coding")
    assert evidence.verified
    assert runner.calls == [["open", "spotify:search:focus%20mix%20%26%20coding"]]


def test_file_search_and_read_are_confined(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    note = allowed / "Friday Notes.txt"
    note.write_text("safe content", encoding="utf-8")
    service = ScopedFileService([allowed])
    assert service.search("notes")[0]["path"] == str(note)
    assert service.read_text(note)["content"] == "safe content"
    with pytest.raises(PermissionError):
        service.read_text(tmp_path / "outside.txt")


def test_hidden_binary_and_oversized_files_are_not_exposed(tmp_path: Path):
    (tmp_path / ".secret.txt").write_text("secret", encoding="utf-8")
    binary = tmp_path / "binary.bin"
    binary.write_bytes(b"abc\x00def")
    large = tmp_path / "large.txt"
    large.write_bytes(b"x" * (ScopedFileService.MAX_TEXT_BYTES + 1))
    service = ScopedFileService([tmp_path])
    assert service.search("secret") == []
    with pytest.raises(ValueError, match="Binary"):
        service.read_text(binary)
    with pytest.raises(ValueError, match="limit"):
        service.read_text(large)
