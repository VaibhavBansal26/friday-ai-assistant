from __future__ import annotations

import mimetypes
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import quote


class DeviceRunner(Protocol):
    def run(self, command: list[str]) -> tuple[int, str, str]: ...


class SubprocessDeviceRunner:
    def run(self, command: list[str]) -> tuple[int, str, str]:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return completed.returncode, completed.stdout, completed.stderr


@dataclass(frozen=True)
class DeviceEvidence:
    action: str
    target: str
    exit_code: int
    verified: bool


class MacOSDeviceService:
    ALLOWED_APPS = {
        "Music",
        "TV",
        "Safari",
        "Google Chrome",
        "Spotify",
        "VLC",
        "QuickTime Player",
    }
    MEDIA_APPS = {"Music", "Spotify"}

    def __init__(self, runner: DeviceRunner | None = None) -> None:
        self.runner = runner or SubprocessDeviceRunner()

    def open_app(self, app_name: str) -> DeviceEvidence:
        if app_name not in self.ALLOWED_APPS:
            raise PermissionError("Application is not on Friday's allowlist")
        code, _, _ = self.runner.run(["open", "-a", app_name])
        return DeviceEvidence("open_app", app_name, code, code == 0)

    def media_control(self, app_name: str, command: str) -> DeviceEvidence:
        if app_name not in self.MEDIA_APPS:
            raise PermissionError("Media control is not allowed for this application")
        scripts = {
            "play_pause": f'tell application "{app_name}" to playpause',
            "next": f'tell application "{app_name}" to next track',
            "previous": f'tell application "{app_name}" to previous track',
        }
        if command not in scripts:
            raise ValueError("Unsupported media command")
        code, _, _ = self.runner.run(["osascript", "-e", scripts[command]])
        return DeviceEvidence("media_control", f"{app_name}:{command}", code, code == 0)

    def spotify_search(self, query: str) -> DeviceEvidence:
        normalized = " ".join(query.split())
        if not normalized or len(normalized) > 200:
            raise ValueError("Spotify search must contain 1 to 200 characters")
        target = f"spotify:search:{quote(normalized, safe='')}"
        code, _, _ = self.runner.run(["open", target])
        return DeviceEvidence("spotify_search", normalized, code, code == 0)


class ScopedFileService:
    MAX_TEXT_BYTES = 200_000

    def __init__(self, allowed_roots: list[Path]) -> None:
        roots = [root.expanduser().resolve() for root in allowed_roots]
        if not roots:
            raise ValueError("At least one file root must be authorized")
        self.allowed_roots = roots

    def resolve(self, value: str | Path) -> Path:
        candidate = Path(value).expanduser().resolve()
        if not any(candidate == root or root in candidate.parents for root in self.allowed_roots):
            raise PermissionError("Path is outside Friday's authorized file roots")
        return candidate

    def search(self, query: str, limit: int = 50) -> list[dict[str, object]]:
        normalized = query.strip().casefold()
        if len(normalized) < 2:
            raise ValueError("File search requires at least two characters")
        results: list[dict[str, object]] = []
        for root in self.allowed_roots:
            for path in root.rglob("*"):
                if len(results) >= min(limit, 100):
                    return results
                if any(part.startswith(".") for part in path.relative_to(root).parts):
                    continue
                if not path.is_file() or normalized not in path.name.casefold():
                    continue
                stat = path.stat()
                results.append(
                    {
                        "path": str(path),
                        "name": path.name,
                        "size": stat.st_size,
                        "mime_type": mimetypes.guess_type(path.name)[0],
                    }
                )
        return results

    def read_text(self, value: str | Path) -> dict[str, object]:
        path = self.resolve(value)
        if not path.is_file():
            raise FileNotFoundError(path)
        size = path.stat().st_size
        if size > self.MAX_TEXT_BYTES:
            raise ValueError("File exceeds Friday's safe text-read limit")
        data = path.read_bytes()
        if b"\x00" in data:
            raise ValueError("Binary files cannot be read as text")
        return {"path": str(path), "content": data.decode("utf-8"), "size": size}
