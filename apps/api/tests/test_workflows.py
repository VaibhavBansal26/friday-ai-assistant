from uuid import uuid4

import pytest

from friday.domain.models import RetryClass, WorkflowStatus
from friday.services.workflows import N8nTriggerVerifier, WorkflowService


def test_irreversible_workflow_allows_only_one_automatic_attempt():
    with pytest.raises(ValueError, match="exactly one"):
        WorkflowService().create(uuid4(), "application", "app-1", RetryClass.IRREVERSIBLE, 2, 60)


def test_workflow_creation_is_idempotent():
    service = WorkflowService()
    first = service.create(uuid4(), "job-monitor", "monitor-1", RetryClass.SAFE, 3, 60)
    second = service.create(uuid4(), "job-monitor", "monitor-1", RetryClass.SAFE, 3, 60)
    assert first.id == second.id


def test_approval_interrupt_blocks_start_without_decision():
    service = WorkflowService()
    run = service.create(uuid4(), "email-send", "email-1", RetryClass.IRREVERSIBLE, 1, 60)
    service.wait_for_approval(run.id, uuid4())
    with pytest.raises(PermissionError, match="waiting for approval"):
        service.start(run.id)
    assert service.start(run.id, approved=True).attempt_count == 1


def test_completion_requires_verification_state():
    service = WorkflowService()
    run = service.create(uuid4(), "task", "task-1", RetryClass.SAFE, 2, 60)
    service.start(run.id)
    with pytest.raises(ValueError, match="verifying"):
        service.complete(run.id, True)
    service.begin_verification(run.id)
    assert service.complete(run.id, True).status == WorkflowStatus.COMPLETED


def test_failed_verification_never_marks_completed():
    service = WorkflowService()
    run = service.create(uuid4(), "publish", "publish-1", RetryClass.IRREVERSIBLE, 1, 60)
    service.start(run.id)
    service.begin_verification(run.id)
    assert service.complete(run.id, False).status == WorkflowStatus.FAILED


def test_observed_side_effect_uses_compensation():
    service = WorkflowService()
    run = service.create(
        uuid4(), "calendar-create", "event-1", RetryClass.CONDITIONAL, 2, 60, "delete_event"
    )
    service.start(run.id)
    assert service.fail(run.id, "downstream failure", True).status == WorkflowStatus.COMPENSATING


def test_n8n_trigger_requires_valid_signature():
    verifier = N8nTriggerVerifier(b"test-secret")
    body = b'{"workflow":"daily-briefing"}'
    assert verifier.verify(body, verifier.sign(body))["workflow"] == "daily-briefing"
    with pytest.raises(PermissionError, match="signature"):
        verifier.verify(body, "invalid")


def test_n8n_cannot_supply_approval_or_credentials():
    verifier = N8nTriggerVerifier(b"test-secret")
    body = b'{"workflow":"publish","approval_status":"approved"}'
    with pytest.raises(PermissionError, match="forbidden"):
        verifier.verify(body, verifier.sign(body))
