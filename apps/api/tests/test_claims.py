from datetime import UTC, datetime

from friday.domain.models import Claim, Provenance
from friday.services.claims import ClaimValidator


def test_verified_fact_requires_source_and_time():
    claim = Claim(text="Tests passed", provenance=Provenance.VERIFIED)
    errors = ClaimValidator().validate(claim)
    assert "source_id is required for verified or retrieved facts" in errors
    assert "verified_at is required for verified facts" in errors


def test_inference_cannot_be_marked_verified():
    claim = Claim(
        text="The company may sponsor visas",
        provenance=Provenance.INFERENCE,
        verified_at=datetime.now(UTC),
    )
    assert ClaimValidator().validate(claim) == ["non-facts cannot have verified_at"]


def test_sourced_verified_fact_is_valid():
    claim = Claim(
        text="Nine tests passed",
        provenance=Provenance.VERIFIED,
        source_id="pytest-run-1",
        verified_at=datetime.now(UTC),
    )
    assert ClaimValidator().validate(claim) == []

