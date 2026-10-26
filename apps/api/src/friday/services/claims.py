from friday.domain.models import Claim, Provenance


class ClaimValidator:
    """Rejects fact-shaped claims that lack the evidence required by their label."""

    def validate(self, claim: Claim) -> list[str]:
        errors: list[str] = []
        if claim.provenance in {Provenance.VERIFIED, Provenance.RETRIEVED} and not claim.source_id:
            errors.append("source_id is required for verified or retrieved facts")
        if claim.provenance == Provenance.VERIFIED and claim.verified_at is None:
            errors.append("verified_at is required for verified facts")
        if claim.provenance in {Provenance.INFERENCE, Provenance.RECOMMENDATION, Provenance.UNKNOWN}:
            if claim.verified_at is not None:
                errors.append("non-facts cannot have verified_at")
        return errors

    def assert_valid(self, claims: list[Claim]) -> None:
        failures = [error for claim in claims for error in self.validate(claim)]
        if failures:
            raise ValueError("; ".join(failures))

