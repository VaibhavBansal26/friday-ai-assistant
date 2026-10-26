from friday.domain.models import ActionRequest, RiskLevel, ToolEvidence, VerificationResult


class VerificationEngine:
    REQUIRED_BY_ACTION = {
        "send_email": ("result_id", "resulting_state"),
        "submit_application": ("result_id", "resulting_state"),
        "push_code": ("result_id", "resulting_state"),
        "create_pull_request": ("result_id", "result_url"),
        "publish_content": ("result_id", "result_url", "resulting_state"),
        "deploy": ("result_id", "result_url", "resulting_state"),
    }

    def verify(self, action: ActionRequest, evidence: list[ToolEvidence]) -> VerificationResult:
        matching = [item for item in evidence if item.action_id == action.id and item.success]
        if not matching:
            return VerificationResult(
                verified=False,
                outcome="failed",
                missing_evidence=["successful trusted tool result"],
            )
        required = self.REQUIRED_BY_ACTION.get(action.action, ("resulting_state",))
        missing = [field for field in required if not any(getattr(item, field) for item in matching)]
        if action.risk >= RiskLevel.HIGH_IMPACT and not any(item.result_id for item in matching):
            if "result_id" not in missing:
                missing.append("result_id")
        return VerificationResult(
            verified=not missing,
            outcome="completed" if not missing else "unverified",
            evidence_ids=[item.tool_run_id for item in matching],
            missing_evidence=missing,
        )

