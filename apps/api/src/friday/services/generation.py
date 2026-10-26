from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from openai import AsyncOpenAI

from friday.core.config import Settings
from friday.domain.models import Claim, Provenance
from friday.services.policy import UNTRUSTED_CONTENT_RULE


SYSTEM_INSTRUCTIONS = f"""You are Friday, a calm and direct personal AI operating system.

Reliability rules:
- Never invent personal facts, external results, citations, identifiers, dates, or metrics.
- Clearly distinguish facts, user-provided information, inferences, recommendations, and unknowns.
- Never claim an action completed without trusted tool evidence.
- Never execute or imply external writes from this text-only generation call.
- If verified information is missing, say that you do not have enough verified information.
- {UNTRUSTED_CONTENT_RULE}
- Do not reveal hidden reasoning. Provide only concise conclusions and user-safe execution stages.
"""


@dataclass(frozen=True)
class GenerationResult:
    text: str
    provider: str
    model: str
    response_id: str | None
    claims: list[Claim]


class TextGenerator(Protocol):
    async def generate(self, user_text: str, model: str) -> GenerationResult: ...


class OpenAIResponsesGenerator:
    """Trusted adapter; the API key is resolved here and never returned to callers."""

    def __init__(self, settings: Settings, client: AsyncOpenAI | None = None) -> None:
        self.settings = settings
        if client is not None:
            self.client = client
            return
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is not configured")
        self.client = AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value())

    async def generate(self, user_text: str, model: str) -> GenerationResult:
        if not user_text.strip():
            raise ValueError("Message cannot be empty")
        response = await self.client.responses.create(
            model=model,
            instructions=SYSTEM_INSTRUCTIONS,
            input=user_text,
        )
        text = response.output_text.strip()
        if not text:
            raise RuntimeError("Model provider returned no text")
        return GenerationResult(
            text=text,
            provider="openai",
            model=model,
            response_id=getattr(response, "id", None),
            claims=[Claim(text=text, provenance=Provenance.INFERENCE)],
        )

