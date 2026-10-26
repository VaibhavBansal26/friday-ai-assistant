from datetime import UTC, datetime, timedelta
from uuid import UUID

from friday.domain.models import (
    ConceptStatus,
    InterviewAnswerEvaluation,
    LearningConcept,
    StudySession,
    StudySessionCreate,
)


class LearningService:
    def __init__(self) -> None:
        self.concepts: dict[UUID, LearningConcept] = {}
        self.sessions: dict[UUID, StudySession] = {}

    def create_concept(self, user_id: UUID, name: str) -> LearningConcept:
        if not name.strip():
            raise ValueError("Concept name cannot be empty")
        concept = LearningConcept(user_id=user_id, name=name.strip())
        self.concepts[concept.id] = concept
        return concept

    def plan_session(self, user_id: UUID, payload: StudySessionCreate) -> StudySession:
        for concept_id in payload.concept_ids:
            concept = self.concepts.get(concept_id)
            if concept is None or concept.user_id != user_id:
                raise ValueError("Study session contains an unknown or unowned concept")
        session = StudySession(user_id=user_id, **payload.model_dump())
        self.sessions[session.id] = session
        return session

    def complete_session(
        self, user_id: UUID, session_id: UUID, score: float, mistakes: list[str]
    ) -> StudySession:
        session = self.sessions[session_id]
        if session.user_id != user_id:
            raise PermissionError("Study session belongs to another user")
        if not 0 <= score <= 1:
            raise ValueError("Score must be between zero and one")
        now = datetime.now(UTC)
        session.status = "completed"
        session.score = score
        session.completed_at = now
        for concept_id in session.concept_ids:
            concept = self.concepts[concept_id]
            concept.accuracy = score
            concept.last_reviewed_at = now
            concept.common_mistakes = list(dict.fromkeys(concept.common_mistakes + mistakes))
            if score >= 0.9:
                concept.status = ConceptStatus.MASTERED
                concept.confidence = "high"
                concept.next_review_at = now + timedelta(days=14)
            elif score >= 0.7:
                concept.status = ConceptStatus.REVIEW
                concept.confidence = "medium"
                concept.next_review_at = now + timedelta(days=3)
            else:
                concept.status = ConceptStatus.LEARNING
                concept.confidence = "low"
                concept.next_review_at = now + timedelta(days=1)
        return session

    def review_tasks_from_interview(
        self, user_id: UUID, evaluation: InterviewAnswerEvaluation
    ) -> list[LearningConcept]:
        return [self.create_concept(user_id, topic) for topic in evaluation.topics_to_review]


class InterviewEvaluationService:
    REQUIRED_EVIDENCE_FIELDS = {
        "strengths",
        "missing_details",
        "incorrect_statements",
        "likely_followups",
        "topics_to_review",
    }

    def validate(self, evaluation: InterviewAnswerEvaluation) -> None:
        if not any(
            getattr(evaluation, field)
            for field in self.REQUIRED_EVIDENCE_FIELDS
        ):
            raise ValueError("Interview evaluation requires evidence-based feedback")

    def overall_score(self, evaluation: InterviewAnswerEvaluation) -> float:
        self.validate(evaluation)
        values = [
            evaluation.correctness,
            evaluation.technical_depth,
            evaluation.structure,
            evaluation.clarity,
            evaluation.relevance,
            evaluation.tradeoff_awareness,
            evaluation.ownership,
            evaluation.evidence_use,
            evaluation.followup_handling,
        ]
        return round(sum(values) / len(values), 2)

