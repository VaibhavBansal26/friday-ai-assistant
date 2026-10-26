from __future__ import annotations

import shutil
from dataclasses import asdict, dataclass
from pathlib import Path

from friday.services.agents import AGENT_REGISTRY, AgentRoute, route_request


@dataclass(frozen=True)
class CapabilityReadiness:
    ready: bool
    reason: str
    approval_required: bool = False


class CapabilityCatalog:
    """Live, secret-free view of which registered capabilities can execute now."""

    def __init__(self, repository_root: Path, linkedin_connected: bool = False) -> None:
        self.repository_root = repository_root.resolve()
        self.linkedin_connected = linkedin_connected

    def readiness(self, route: AgentRoute) -> CapabilityReadiness:
        group = route.tool_group
        if group == "spotify":
            installed = Path("/Applications/Spotify.app").exists()
            return CapabilityReadiness(installed, "Spotify is installed" if installed else "Install Spotify")
        if group in {"browser-read", "browser-form"}:
            installed = Path("/Applications/Google Chrome.app").exists()
            return CapabilityReadiness(installed, "Chrome adapter is available" if installed else "Install Google Chrome", group == "browser-form")
        if group in {"repository-read", "repository-write", "github-write"}:
            available = (self.repository_root / ".git").exists()
            approval = group == "github-write"
            return CapabilityReadiness(available, "Repository is available" if available else "Open a Git repository", approval)
        if route.agent == "linkedin":
            return CapabilityReadiness(self.linkedin_connected, "LinkedIn is connected" if self.linkedin_connected else "Connect LinkedIn", True)
        if group == "knowledge-read":
            available = shutil.which("qmd") is not None
            return CapabilityReadiness(available, "QMD is available" if available else "Install or configure QMD")
        return CapabilityReadiness(True, "Local capability is available", route.risk >= 2)

    def inspect(self, command: str) -> dict[str, object]:
        route = route_request(command)
        readiness = self.readiness(route)
        agent = AGENT_REGISTRY[route.agent]
        return {
            "route": asdict(route),
            "readiness": asdict(readiness),
            "agent": {
                "name": agent.name,
                "purpose": agent.purpose,
                "tool_groups": sorted(agent.tool_groups),
                "maximum_risk": int(agent.maximum_risk),
            },
        }
