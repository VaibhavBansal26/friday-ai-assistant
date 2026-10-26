import hashlib
from pathlib import Path
from uuid import UUID

from friday.domain.models import (
    GraphImpactSuggestion,
    RelationshipAuthority,
    RelationshipProposal,
    RepositoryGraphEdge,
)


class GBrainGovernanceService:
    """Experimental relationship memory. All outputs begin in shadow mode."""

    def __init__(self) -> None:
        self.proposals: dict[UUID, RelationshipProposal] = {}

    def propose(
        self,
        user_id: UUID,
        subject: str,
        predicate: str,
        object_value: str,
        source_ids: list[str],
        confidence: str,
    ) -> RelationshipProposal:
        if not source_ids:
            raise ValueError("Relationship proposal requires at least one source")
        proposal = RelationshipProposal(
            user_id=user_id,
            subject=subject,
            predicate=predicate,
            object=object_value,
            authority=RelationshipAuthority.MEMORY_INFERRED,
            source_ids=source_ids,
            confidence=confidence,
            status="shadow",
        )
        self.proposals[proposal.id] = proposal
        return proposal

    def mark_verified(self, proposal_id: UUID) -> None:
        raise PermissionError(
            "GBrain proposals cannot become verified facts; confirm through the fact registry"
        )


class GraphifyGovernanceService:
    """Read-only repository graph. Source files remain authoritative."""

    def __init__(self, repository_root: Path) -> None:
        self.repository_root = repository_root.resolve()

    def impact(self, changed_path: str, edges: list[RepositoryGraphEdge]) -> GraphImpactSuggestion:
        changed = self._resolve(changed_path)
        verified: list[str] = []
        unverified: list[str] = []
        related = sorted(
            {
                edge.target_path
                for edge in edges
                if edge.source_path == changed_path
            }
            | {
                edge.source_path
                for edge in edges
                if edge.target_path == changed_path
            }
        )
        for path in related:
            resolved = self._resolve(path)
            matching_edges = [
                edge
                for edge in edges
                if {edge.source_path, edge.target_path} == {changed_path, path}
            ]
            expected_hashes = {
                edge.target_hash if edge.target_path == path else edge.source_hash
                for edge in matching_edges
            }
            actual_hash = self._hash(resolved) if resolved.is_file() else None
            if actual_hash and actual_hash in expected_hashes:
                verified.append(path)
            else:
                unverified.append(path)
        return GraphImpactSuggestion(
            changed_path=str(changed.relative_to(self.repository_root)),
            related_paths=related,
            verified_paths=verified,
            unverified_paths=unverified,
            may_authorize_edit=False,
        )

    def _resolve(self, path: str) -> Path:
        resolved = (self.repository_root / path).resolve()
        if resolved != self.repository_root and self.repository_root not in resolved.parents:
            raise PermissionError("Graph path is outside the repository")
        return resolved

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

