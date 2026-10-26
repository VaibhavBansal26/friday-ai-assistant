from uuid import uuid4

import pytest

from friday.domain.models import RiskLevel, WebsitePage, WebsiteProjectCreate, WebsiteQaEvidence
from friday.services.websites import WebsiteService


def project():
    return WebsiteProjectCreate(
        name="Portfolio",
        audience="AI engineering hiring teams",
        goal="Present verified projects",
        pages=[WebsitePage(path="/", title="Home", purpose="Overview")],
    )


def test_website_requires_unique_valid_paths():
    payload = project()
    payload.pages.append(WebsitePage(path="/", title="Duplicate", purpose="Invalid"))
    with pytest.raises(ValueError, match="unique"):
        WebsiteService().create_project(uuid4(), payload)


def test_website_is_not_complete_without_browser_evidence():
    service = WebsiteService()
    item = service.create_project(uuid4(), project())
    result = service.verify_local_preview(WebsiteQaEvidence(project_id=item.id))
    assert not result.verified
    assert "verified local preview URL" in result.missing_evidence
    assert "passing production build" in result.missing_evidence


def test_complete_responsive_accessible_preview_is_verified():
    service = WebsiteService()
    item = service.create_project(uuid4(), project())
    result = service.verify_local_preview(
        WebsiteQaEvidence(
            project_id=item.id,
            preview_url="http://127.0.0.1:3000",
            tested_viewports=["mobile", "tablet", "desktop"],
            screenshot_ids=["mobile.png", "tablet.png", "desktop.png"],
            test_exit_code=0,
            build_exit_code=0,
        )
    )
    assert result.verified


def test_deployment_is_separate_level_three_action():
    service = WebsiteService()
    user_id = uuid4()
    item = service.create_project(user_id, project())
    action = service.deployment_action(user_id, item.id)
    assert action.risk == RiskLevel.HIGH_IMPACT
    assert action.action == "deploy"
    assert item.status == "planned"
