import hashlib
from pathlib import Path
from uuid import uuid4

import pytest

from friday.domain.models import RelationshipAuthority, RepositoryGraphEdge
from friday.services.advanced_memory import GBrainGovernanceService, GraphifyGovernanceService


def test_gbrain_proposal_is_shadow_inference_not_verified_fact():
    service = GBrainGovernanceService()
    proposal = service.propose(
        uuid4(),
        "user",
        "prefers",
        "concise replies",
        ["conversation-1"],
        "medium",
    )
    assert proposal.status == "shadow"
    assert proposal.authority == RelationshipAuthority.MEMORY_INFERRED
    with pytest.raises(PermissionError, match="fact registry"):
        service.mark_verified(proposal.id)


def test_gbrain_requires_source_provenance():
    with pytest.raises(ValueError, match="source"):
        GBrainGovernanceService().propose(
            uuid4(), "user", "prefers", "concise replies", [], "unknown"
        )


def test_graphify_edge_is_verified_against_current_source_hash(tmp_path: Path):
    (tmp_path / "app.py").write_text("from service import run\n")
    target = tmp_path / "service.py"
    target.write_text("def run(): return True\n")
    target_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    suggestion = GraphifyGovernanceService(tmp_path).impact(
        "app.py",
        [
            RepositoryGraphEdge(
                source_path="app.py",
                target_path="service.py",
                relationship="imports",
                target_hash=target_hash,
            )
        ],
    )
    assert suggestion.verified_paths == ["service.py"]
    assert not suggestion.may_authorize_edit


def test_stale_graph_hash_is_unverified(tmp_path: Path):
    (tmp_path / "app.py").write_text("import service\n")
    (tmp_path / "service.py").write_text("changed\n")
    suggestion = GraphifyGovernanceService(tmp_path).impact(
        "app.py",
        [
            RepositoryGraphEdge(
                source_path="app.py",
                target_path="service.py",
                relationship="imports",
                target_hash="stale-hash",
            )
        ],
    )
    assert suggestion.unverified_paths == ["service.py"]


def test_graph_path_escape_is_denied(tmp_path: Path):
    with pytest.raises(PermissionError, match="outside"):
        GraphifyGovernanceService(tmp_path).impact(
            "../secret.py",
            [RepositoryGraphEdge(source_path="../secret.py", target_path="app.py", relationship="x")],
        )
