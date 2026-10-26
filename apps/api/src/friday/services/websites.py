import re
from uuid import UUID

from friday.domain.models import (
    ActionRequest,
    RiskLevel,
    VerificationResult,
    WebsiteProject,
    WebsiteProjectCreate,
    WebsiteQaEvidence,
)


class WebsiteService:
    REQUIRED_STACK = {"Next.js", "React", "TypeScript"}

    def __init__(self) -> None:
        self.projects: dict[UUID, WebsiteProject] = {}

    def create_project(self, user_id: UUID, payload: WebsiteProjectCreate) -> WebsiteProject:
        if not self.REQUIRED_STACK.issubset(set(payload.stack)):
            raise ValueError("Website project is missing the required production stack")
        paths = [page.path for page in payload.pages]
        if len(paths) != len(set(paths)):
            raise ValueError("Website page paths must be unique")
        if any(not re.fullmatch(r"/(?:[a-z0-9-]+/?)*", path) for path in paths):
            raise ValueError("Website page path is invalid")
        project = WebsiteProject(user_id=user_id, **payload.model_dump())
        self.projects[project.id] = project
        return project

    def verify_local_preview(self, evidence: WebsiteQaEvidence) -> VerificationResult:
        if evidence.project_id not in self.projects:
            raise KeyError(evidence.project_id)
        missing: list[str] = []
        if not evidence.preview_url or not evidence.preview_url.startswith(
            ("http://localhost", "http://127.0.0.1")
        ):
            missing.append("verified local preview URL")
        required_viewports = {"mobile", "tablet", "desktop"}
        if not required_viewports.issubset(set(evidence.tested_viewports)):
            missing.append("mobile, tablet, and desktop viewport checks")
        if len(evidence.screenshot_ids) < 3:
            missing.append("visual screenshots for responsive viewports")
        if evidence.accessibility_violations:
            missing.append("zero accessibility violations")
        if evidence.broken_links:
            missing.append("zero broken links")
        if evidence.console_errors:
            missing.append("zero browser console errors")
        if evidence.test_exit_code != 0:
            missing.append("passing test command")
        if evidence.build_exit_code != 0:
            missing.append("passing production build")
        return VerificationResult(
            verified=not missing,
            outcome="completed" if not missing else "unverified",
            missing_evidence=missing,
        )

    def deployment_action(self, user_id: UUID, project_id: UUID) -> ActionRequest:
        project = self.projects[project_id]
        if project.user_id != user_id:
            raise PermissionError("Website project belongs to another user")
        return ActionRequest(
            agent="website-builder",
            action="deploy",
            target=project.name,
            risk=RiskLevel.HIGH_IMPACT,
            data_transmitted=["source code", "build output", "deployment metadata"],
            reversible=True,
            expected_outcome="Deployment provider returns a successful deployment ID and URL",
            idempotency_key=f"website-deploy:{project.id}",
            preview=project.model_dump(mode="json"),
        )

