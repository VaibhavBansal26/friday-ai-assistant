from uuid import uuid4

import pytest

from friday.core.config import Settings
from friday.domain.models import Claim, Provenance
from friday.services.conversation import ConversationService
from friday.services.events import EventHub
from friday.services.generation import GenerationResult
from friday.services.model_router import ModelRouter
from friday.services.store import InMemoryStore


class FakeGenerator:
    async def generate(self, user_text: str, model: str) -> GenerationResult:
        return GenerationResult(
            text="I do not have enough verified information.",
            provider="test",
            model=model,
            response_id="test-response",
            claims=[Claim(text="Insufficient information", provenance=Provenance.UNKNOWN)],
        )


@pytest.mark.asyncio
async def test_conversation_persists_user_and_assistant_messages_and_emits_events():
    store = InMemoryStore()
    session = store.create_session(uuid4())
    conversation = store.create_conversation(session.user_id)
    events = EventHub()
    service = ConversationService(
        store, ModelRouter(Settings()), FakeGenerator(), events
    )
    message = await service.respond(conversation.id, session.id, "What is my salary?")
    assert message.content == "I do not have enough verified information."
    assert len(store.messages[conversation.id]) == 2
    assert events._sequence[session.id] == 3

