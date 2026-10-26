from uuid import UUID

from friday.domain.models import (
    AuditEvent,
    Idea,
    IdeaCreate,
    MemoryProposal,
    MemoryProposalCreate,
    MemoryStatus,
    Project,
    ProjectCreate,
    Provenance,
    VerifiedFact,
    VerifiedFactCreate,
    now_utc,
)
from friday.services.store import InMemoryStore


FACT_AUTHORITIES = {
    Provenance.USER_PROVIDED: 100,
    Provenance.VERIFIED: 90,
    Provenance.RETRIEVED: 60,
    Provenance.INFERENCE: 20,
    Provenance.RECOMMENDATION: 10,
    Provenance.UNKNOWN: 0,
}


class KnowledgeService:
    def __init__(self, audit_store: InMemoryStore) -> None:
        self.audit_store = audit_store
        self.projects: dict[UUID, Project] = {}
        self.ideas: dict[UUID, Idea] = {}
        self.facts: dict[UUID, VerifiedFact] = {}
        self.memories: dict[UUID, MemoryProposal] = {}

    def create_project(self, user_id: UUID, payload: ProjectCreate) -> Project:
        project = Project(user_id=user_id, **payload.model_dump())
        self.projects[project.id] = project
        self._audit(user_id, "project.created", "project", project.id)
        return project

    def create_idea(self, user_id: UUID, payload: IdeaCreate) -> Idea:
        idea = Idea(user_id=user_id, **payload.model_dump())
        self.ideas[idea.id] = idea
        self._audit(user_id, "idea.created", "idea", idea.id)
        return idea

    def register_fact(self, user_id: UUID, payload: VerifiedFactCreate) -> VerifiedFact:
        if payload.provenance in {Provenance.INFERENCE, Provenance.RECOMMENDATION, Provenance.UNKNOWN}:
            raise ValueError("Only fact-level provenance can enter the verified fact registry")
        if not payload.source_id:
            raise ValueError("A source is required for the verified fact registry")
        conflicting = [
            fact
            for fact in self.facts.values()
            if fact.user_id == user_id
            and fact.namespace == payload.namespace
            and fact.fact_key == payload.fact_key
            and fact.value != payload.value
        ]
        if conflicting and any(
            FACT_AUTHORITIES[item.provenance] >= FACT_AUTHORITIES[payload.provenance]
            for item in conflicting
        ):
            raise ValueError("A conflicting equal-or-higher-authority fact requires user resolution")
        fact = VerifiedFact(
            user_id=user_id,
            verified_at=now_utc(),
            **payload.model_dump(),
        )
        self.facts[fact.id] = fact
        self._audit(user_id, "fact.registered", "verified_fact", fact.id)
        return fact

    def propose_memory(self, user_id: UUID, payload: MemoryProposalCreate) -> MemoryProposal:
        duplicates = [
            memory
            for memory in self.memories.values()
            if memory.user_id == user_id
            and memory.content.casefold() == payload.content.casefold()
            and memory.status in {MemoryStatus.PROPOSED, MemoryStatus.APPROVED}
        ]
        if duplicates:
            return duplicates[0]
        contradictions = [
            fact.id
            for fact in self.facts.values()
            if fact.user_id == user_id
            and isinstance(fact.value, str)
            and fact.fact_key.casefold() in payload.content.casefold()
            and str(fact.value).casefold() not in payload.content.casefold()
        ]
        memory = MemoryProposal(
            user_id=user_id,
            contradiction_ids=contradictions,
            **payload.model_dump(),
        )
        self.memories[memory.id] = memory
        self._audit(user_id, "memory.proposed", "memory", memory.id)
        return memory

    def decide_memory(self, user_id: UUID, memory_id: UUID, approve: bool) -> MemoryProposal:
        memory = self.memories[memory_id]
        if memory.user_id != user_id:
            raise PermissionError("Memory belongs to another user")
        if approve and memory.contradiction_ids:
            raise ValueError("Contradictory memory requires conflict resolution")
        memory.status = MemoryStatus.APPROVED if approve else MemoryStatus.REJECTED
        self._audit(
            user_id,
            "memory.approved" if approve else "memory.rejected",
            "memory",
            memory.id,
        )
        return memory

    def _audit(self, user_id: UUID, event: str, target_type: str, target_id: UUID) -> None:
        self.audit_store.append_audit(
            AuditEvent(
                user_id=user_id,
                event_type=event,
                actor="user",
                target_type=target_type,
                target_id=str(target_id),
            )
        )

