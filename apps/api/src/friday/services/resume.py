import re
from uuid import UUID

from friday.domain.models import (
    ResumeClaim,
    ResumeClaimCreate,
    ResumeTailoringRequest,
    ResumeTailoringResult,
    TailoredResumeClaim,
    VerifiedFact,
)

NUMBER_PATTERN = re.compile(r"(?<!\w)(?:\d+(?:\.\d+)?%?|\$\d[\d,.]*)(?!\w)")


class ResumeService:
    def __init__(self) -> None:
        self.claims: dict[UUID, ResumeClaim] = {}

    def register_claim(
        self, user_id: UUID, payload: ResumeClaimCreate, facts: dict[UUID, VerifiedFact]
    ) -> ResumeClaim:
        fact = facts.get(payload.verified_fact_id)
        if fact is None or fact.user_id != user_id:
            raise ValueError("Resume claim requires an owned verified fact")
        if payload.source_excerpt.strip() not in str(fact.value):
            raise ValueError("Source excerpt is not present in the verified fact")
        claim = ResumeClaim(user_id=user_id, **payload.model_dump())
        self.claims[claim.id] = claim
        return claim

    def tailor(self, user_id: UUID, request: ResumeTailoringRequest) -> ResumeTailoringResult:
        required = {skill.casefold() for skill in request.job.required_skills}
        selected: list[TailoredResumeClaim] = []
        omitted: list[UUID] = []
        supported_skills: set[str] = set()
        warnings: list[str] = []
        for claim_id in request.claim_ids:
            claim = self.claims.get(claim_id)
            if claim is None or claim.user_id != user_id:
                raise ValueError("Unknown or unowned resume claim")
            matched = sorted(required & {skill.casefold() for skill in claim.skills})
            if required and not matched:
                omitted.append(claim.id)
                continue
            rewrite = request.proposed_rewrites.get(claim.id, claim.claim_text).strip()
            self._validate_rewrite(claim, rewrite)
            claim_skills = {skill.casefold() for skill in claim.skills}
            unsupported_mentions = [
                skill
                for skill in required - claim_skills
                if skill in rewrite.casefold()
            ]
            if unsupported_mentions:
                raise ValueError(
                    "Rewrite introduces unsupported technologies: "
                    + ", ".join(sorted(unsupported_mentions))
                )
            supported_skills.update(skill.casefold() for skill in claim.skills)
            selected.append(
                TailoredResumeClaim(
                    source_claim_id=claim.id,
                    verified_fact_id=claim.verified_fact_id,
                    original_text=claim.claim_text,
                    tailored_text=rewrite,
                    matched_skills=matched,
                    transformation_note=(
                        "Original verified wording"
                        if rewrite == claim.claim_text
                        else "Meaning-preserving rewrite"
                    ),
                )
            )
        missing = sorted(required - supported_skills)
        if missing:
            warnings.append("Required skills are missing and were not added: " + ", ".join(missing))
        return ResumeTailoringResult(
            job_id=request.job.id,
            selected_claims=selected,
            omitted_claim_ids=omitted,
            missing_required_skills=missing,
            warnings=warnings,
        )

    @staticmethod
    def _validate_rewrite(claim: ResumeClaim, rewrite: str) -> None:
        invented = set(NUMBER_PATTERN.findall(rewrite)) - set(
            NUMBER_PATTERN.findall(claim.claim_text)
        )
        if invented:
            raise ValueError("Rewrite introduces unsupported metrics: " + ", ".join(sorted(invented)))
