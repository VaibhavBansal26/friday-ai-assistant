from uuid import uuid4

import pytest

from friday.domain.models import (
    ConceptStatus,
    InterviewAnswerEvaluation,
    StudySessionCreate,
)
from friday.services.learning import InterviewEvaluationService, LearningService


def evaluation(**changes):
    values = {
        "correctness": 3,
        "technical_depth": 3,
        "structure": 3,
        "clarity": 3,
        "relevance": 3,
        "tradeoff_awareness": 3,
        "ownership": 3,
        "evidence_use": 3,
        "followup_handling": 3,
        "topics_to_review": ["consistent hashing"],
    }
    values.update(changes)
    return InterviewAnswerEvaluation(**values)


def test_study_session_requires_active_exercise_and_completion_criteria():
    with pytest.raises(Exception):
        StudySessionCreate(concept_ids=[], objective="Learn RAG", exercise="", completion_criteria=[])


def test_low_score_schedules_next_day_review_and_tracks_mistakes():
    service = LearningService()
    user_id = uuid4()
    concept = service.create_concept(user_id, "vector retrieval")
    session = service.plan_session(
        user_id,
        StudySessionCreate(
            concept_ids=[concept.id],
            objective="Explain retrieval",
            exercise="Implement cosine similarity",
            completion_criteria=["passes example cases"],
        ),
    )
    service.complete_session(user_id, session.id, 0.5, ["confused distance with similarity"])
    assert concept.status == ConceptStatus.LEARNING
    assert concept.confidence == "low"
    assert concept.next_review_at is not None
    assert concept.common_mistakes == ["confused distance with similarity"]


def test_high_score_marks_mastered_but_schedules_future_review():
    service = LearningService()
    user_id = uuid4()
    concept = service.create_concept(user_id, "attention")
    session = service.plan_session(
        user_id,
        StudySessionCreate(
            concept_ids=[concept.id],
            objective="Derive attention",
            exercise="Calculate scaled dot-product attention",
            completion_criteria=["correct derivation"],
        ),
    )
    service.complete_session(user_id, session.id, 0.95, [])
    assert concept.status == ConceptStatus.MASTERED
    assert concept.next_review_at is not None


def test_interview_evaluation_requires_feedback_evidence():
    empty = evaluation(topics_to_review=[])
    with pytest.raises(ValueError, match="evidence-based"):
        InterviewEvaluationService().overall_score(empty)


def test_interview_topics_create_study_concepts():
    service = LearningService()
    concepts = service.review_tasks_from_interview(uuid4(), evaluation())
    assert [concept.name for concept in concepts] == ["consistent hashing"]
