from uuid import uuid4

import pytest

from friday.domain.models import (
    IdeaCreate,
    MemoryProposalCreate,
    MemoryStatus,
    ProjectCreate,
    Provenance,
    VerifiedFactCreate,
)
from friday.services.knowledge import KnowledgeService
from friday.services.store import InMemoryStore


def test_project_and_idea_are_explicit_not_automatically_linked():
    service = KnowledgeService(InMemoryStore())
    user_id = uuid4()
    project = service.create_project(user_id, ProjectCreate(name="Friday"))
    idea = service.create_idea(user_id, IdeaCreate(problem="Assist safely"))
    assert project.id != idea.id
    assert not hasattr(idea, "project_id")


def test_inference_cannot_enter_verified_fact_registry():
    service = KnowledgeService(InMemoryStore())
    with pytest.raises(ValueError, match="fact-level provenance"):
        service.register_fact(
            uuid4(),
            VerifiedFactCreate(
                namespace="career",
                fact_key="years_experience",
                value=5,
                provenance=Provenance.INFERENCE,
                source_id="model",
            ),
        )


def test_equal_authority_fact_conflict_requires_resolution():
    service = KnowledgeService(InMemoryStore())
    user_id = uuid4()
    service.register_fact(
        user_id,
        VerifiedFactCreate(
            namespace="career",
            fact_key="title",
            value="Engineer",
            provenance=Provenance.USER_PROVIDED,
            source_id="user-confirmation-1",
        ),
    )
    with pytest.raises(ValueError, match="requires user resolution"):
        service.register_fact(
            user_id,
            VerifiedFactCreate(
                namespace="career",
                fact_key="title",
                value="Manager",
                provenance=Provenance.USER_PROVIDED,
                source_id="user-confirmation-2",
            ),
        )


def test_memory_is_proposed_not_silently_approved():
    service = KnowledgeService(InMemoryStore())
    memory = service.propose_memory(
        uuid4(), MemoryProposalCreate(content="Prefers concise replies", source_id="conversation-1")
    )
    assert memory.status == MemoryStatus.PROPOSED


def test_duplicate_memory_returns_existing_proposal():
    service = KnowledgeService(InMemoryStore())
    user_id = uuid4()
    payload = MemoryProposalCreate(content="Prefers concise replies", source_id="conversation-1")
    assert service.propose_memory(user_id, payload).id == service.propose_memory(user_id, payload).id


def test_cross_user_memory_decision_is_denied():
    service = KnowledgeService(InMemoryStore())
    memory = service.propose_memory(
        uuid4(), MemoryProposalCreate(content="Private preference", source_id="conversation-1")
    )
    with pytest.raises(PermissionError):
        service.decide_memory(uuid4(), memory.id, approve=True)

