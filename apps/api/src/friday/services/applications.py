from uuid import UUID

from friday.domain.models import (
    ActionRequest,
    ApplicationDraft,
    ApplicationDraftCreate,
    ApplicationFieldCategory,
    ApplicationReview,
    RiskLevel,
)


class ApplicationService:
    def __init__(self) -> None:
        self.drafts: dict[UUID, ApplicationDraft] = {}

    def create_draft(self, user_id: UUID, payload: ApplicationDraftCreate) -> ApplicationDraft:
        for field in payload.fields:
            if field.value is not None and field.source_fact_id is None:
                if field.category != ApplicationFieldCategory.VOLUNTARY_DEMOGRAPHIC:
                    raise ValueError(f"Field '{field.name}' has a value without a verified source")
            if field.category == ApplicationFieldCategory.VOLUNTARY_DEMOGRAPHIC:
                if field.value is not None:
                    raise ValueError("Voluntary demographic fields must remain unanswered by default")
        draft = ApplicationDraft(user_id=user_id, **payload.model_dump())
        self.drafts[draft.id] = draft
        return draft

    def review(self, user_id: UUID, application_id: UUID) -> ApplicationReview:
        draft = self._owned(user_id, application_id)
        unanswered = [field.name for field in draft.fields if field.required and field.value is None]
        low_confidence = [
            field.name for field in draft.fields if field.value is not None and field.confidence != "high"
        ]
        demographics = [
            field.name
            for field in draft.fields
            if field.category == ApplicationFieldCategory.VOLUNTARY_DEMOGRAPHIC
        ]
        blockers: list[str] = []
        if unanswered:
            blockers.append("Required fields are unanswered")
        if low_confidence:
            blockers.append("Low-confidence answers require confirmation")
        if not draft.uploaded_files:
            blockers.append("No approved resume file is attached")
        return ApplicationReview(
            application_id=draft.id,
            company=draft.job.company,
            role=draft.job.title,
            application_url=draft.application_url,
            resume_version_id=draft.resume_version_id,
            fields=draft.fields,
            uploaded_files=draft.uploaded_files,
            unanswered_fields=unanswered,
            low_confidence_fields=low_confidence,
            voluntary_demographic_fields=demographics,
            ready_for_approval=not blockers,
            blockers=blockers,
        )

    def submission_action(self, user_id: UUID, application_id: UUID) -> ActionRequest:
        draft = self._owned(user_id, application_id)
        review = self.review(user_id, application_id)
        if not review.ready_for_approval:
            raise ValueError("Application review has unresolved blockers")
        return ActionRequest(
            agent="job-application-agent",
            action="submit_application",
            target=f"{draft.job.company} — {draft.job.title}",
            risk=RiskLevel.HIGH_IMPACT,
            data_transmitted=[field.name for field in draft.fields if field.value is not None]
            + draft.uploaded_files,
            reversible=False,
            expected_outcome="ATS returns a durable application confirmation",
            idempotency_key=f"application-submit:{draft.id}",
            preview=review.model_dump(mode="json"),
        )

    def _owned(self, user_id: UUID, application_id: UUID) -> ApplicationDraft:
        draft = self.drafts[application_id]
        if draft.user_id != user_id:
            raise PermissionError("Application belongs to another user")
        return draft

