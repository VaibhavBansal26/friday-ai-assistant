import hashlib
import hmac
import json
from uuid import UUID

from friday.domain.models import RetryClass, WorkflowRun, WorkflowStatus, now_utc


class WorkflowService:
    def __init__(self) -> None:
        self.runs: dict[UUID, WorkflowRun] = {}
        self.idempotency: dict[str, UUID] = {}

    def create(
        self,
        user_id: UUID,
        workflow_type: str,
        idempotency_key: str,
        retry_class: RetryClass,
        maximum_attempts: int,
        timeout_seconds: int,
        compensation_action: str | None = None,
    ) -> WorkflowRun:
        existing = self.idempotency.get(idempotency_key)
        if existing:
            return self.runs[existing]
        if retry_class == RetryClass.IRREVERSIBLE and maximum_attempts != 1:
            raise ValueError("Irreversible workflows must have exactly one automatic attempt")
        run = WorkflowRun(
            user_id=user_id,
            workflow_type=workflow_type,
            idempotency_key=idempotency_key,
            retry_class=retry_class,
            maximum_attempts=maximum_attempts,
            timeout_seconds=timeout_seconds,
            compensation_action=compensation_action,
        )
        self.runs[run.id] = run
        self.idempotency[idempotency_key] = run.id
        return run

    def wait_for_approval(self, run_id: UUID, approval_id: UUID) -> WorkflowRun:
        run = self.runs[run_id]
        self._transition(run, WorkflowStatus.WAITING_APPROVAL)
        run.approval_id = approval_id
        return run

    def start(self, run_id: UUID, approved: bool = False) -> WorkflowRun:
        run = self.runs[run_id]
        if run.status == WorkflowStatus.WAITING_APPROVAL and not approved:
            raise PermissionError("Workflow is waiting for approval")
        if run.attempt_count >= run.maximum_attempts:
            raise RuntimeError("Workflow attempt limit reached")
        self._transition(run, WorkflowStatus.RUNNING)
        run.attempt_count += 1
        return run

    def begin_verification(self, run_id: UUID) -> WorkflowRun:
        run = self.runs[run_id]
        self._transition(run, WorkflowStatus.VERIFYING)
        return run

    def complete(self, run_id: UUID, verified: bool) -> WorkflowRun:
        run = self.runs[run_id]
        if run.status != WorkflowStatus.VERIFYING:
            raise ValueError("Workflow must be verifying before completion")
        if not verified:
            run.verification_state = "failed"
            run.status = WorkflowStatus.FAILED
            run.failure_reason = "Outcome verification failed"
            run.updated_at = now_utc()
            return run
        run.verification_state = "verified"
        run.status = WorkflowStatus.COMPLETED
        run.updated_at = now_utc()
        return run

    def fail(self, run_id: UUID, reason: str, side_effect_observed: bool) -> WorkflowRun:
        run = self.runs[run_id]
        run.failure_reason = reason
        if side_effect_observed and run.compensation_action:
            run.status = WorkflowStatus.COMPENSATING
        else:
            run.status = WorkflowStatus.FAILED
        run.updated_at = now_utc()
        return run

    @staticmethod
    def _transition(run: WorkflowRun, target: WorkflowStatus) -> None:
        allowed = {
            WorkflowStatus.PENDING: {WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.RUNNING},
            WorkflowStatus.WAITING_APPROVAL: {WorkflowStatus.RUNNING, WorkflowStatus.CANCELLED},
            WorkflowStatus.RUNNING: {WorkflowStatus.VERIFYING, WorkflowStatus.FAILED},
            WorkflowStatus.FAILED: {WorkflowStatus.RUNNING, WorkflowStatus.COMPENSATING},
        }
        if target not in allowed.get(run.status, set()):
            raise ValueError(f"Invalid workflow transition: {run.status} -> {target}")
        run.status = target
        run.updated_at = now_utc()


class N8nTriggerVerifier:
    """Validates signed triggers. n8n payloads cannot carry approvals or credentials."""

    FORBIDDEN_KEYS = {"approval", "approval_status", "credential", "secret", "token"}

    def __init__(self, signing_secret: bytes) -> None:
        self.signing_secret = signing_secret

    def sign(self, body: bytes) -> str:
        return hmac.new(self.signing_secret, body, hashlib.sha256).hexdigest()

    def verify(self, body: bytes, signature: str) -> dict:
        expected = self.sign(body)
        if not hmac.compare_digest(expected, signature):
            raise PermissionError("Invalid workflow signature")
        payload = json.loads(body)
        forbidden = self.FORBIDDEN_KEYS & {key.casefold() for key in payload}
        if forbidden:
            raise PermissionError("Workflow payload contains forbidden authority or credential fields")
        return payload

