from pathlib import Path

import pytest

from friday.domain.models import BrowserAction, BrowserActionType, BrowserCompletionEvidence
from friday.services.browser import BrowserPolicy


def policy(tmp_path: Path):
    return BrowserPolicy({"example.test"}, tmp_path)


def test_domain_allowlist_blocks_untrusted_navigation(tmp_path: Path):
    result = policy(tmp_path).assess(
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="https://evil.test")
    )
    assert not result.allowed
    assert "allowlisted" in result.reason


def test_private_network_ssrf_is_blocked(tmp_path: Path):
    service = BrowserPolicy({"localhost"}, tmp_path)
    result = service.assess(
        BrowserAction(action_type=BrowserActionType.NAVIGATE, url="http://localhost/admin")
    )
    assert not result.allowed
    assert "Private-network" in result.reason


def test_submission_requires_approval_and_idempotency(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(BrowserPolicy, "_is_private_host", staticmethod(lambda host: False))
    action = BrowserAction(
        action_type=BrowserActionType.SUBMIT,
        url="https://example.test/apply",
        idempotency_key="apply-1",
    )
    result = policy(tmp_path).assess(action)
    assert not result.allowed
    assert result.requires_approval


def test_duplicate_submission_is_blocked(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(BrowserPolicy, "_is_private_host", staticmethod(lambda host: False))
    service = policy(tmp_path)
    service.register_approved_submission("apply-1")
    with pytest.raises(ValueError, match="Duplicate"):
        service.register_approved_submission("apply-1")


def test_upload_must_stay_in_manifest_root(tmp_path: Path):
    with pytest.raises(PermissionError, match="manifest root"):
        policy(tmp_path).validate_upload(tmp_path.parent / "private-resume.pdf")


def test_symlink_upload_is_blocked(tmp_path: Path):
    target = tmp_path / "resume.pdf"
    target.write_text("resume")
    link = tmp_path / "resume-link.pdf"
    link.symlink_to(target)
    with pytest.raises(PermissionError, match="Symlink"):
        policy(tmp_path).validate_upload(link)


def test_captcha_pauses_for_manual_intervention():
    result = BrowserPolicy.captcha_assessment()
    assert not result.allowed
    assert result.requires_manual_intervention


def test_clicking_submit_is_not_completion_evidence():
    result = BrowserPolicy.verify_completion(
        BrowserCompletionEvidence(action_type=BrowserActionType.SUBMIT, clicked_submit=True)
    )
    assert not result.verified
    assert "confirmation page" in result.missing_evidence[0]


def test_confirmation_number_verifies_submission():
    result = BrowserPolicy.verify_completion(
        BrowserCompletionEvidence(
            action_type=BrowserActionType.SUBMIT,
            clicked_submit=True,
            confirmation_number="APP-42",
        )
    )
    assert result.verified
