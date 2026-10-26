from uuid import UUID, uuid4

from friday.domain.models import Message, MessageRole, ModelRouteRequest
from friday.services.events import EventHub
from friday.services.generation import TextGenerator
from friday.services.model_router import ModelRouter
from friday.services.store import InMemoryStore


class ConversationService:
    def __init__(
        self,
        store: InMemoryStore,
        router: ModelRouter,
        generator: TextGenerator,
        events: EventHub,
    ) -> None:
        self.store = store
        self.router = router
        self.generator = generator
        self.events = events

    async def respond(
        self, conversation_id: UUID, session_id: UUID, user_text: str
    ) -> Message:
        correlation_id = uuid4()
        await self.events.publish(
            session_id,
            "execution.stage",
            {"stage": "understanding", "label": "Understanding your request"},
            correlation_id,
        )
        self.store.add_message(conversation_id, MessageRole.USER, user_text)
        route = self.router.route(ModelRouteRequest(task_type="conversation"))
        await self.events.publish(
            session_id,
            "execution.stage",
            {"stage": "thinking", "label": "Preparing a response"},
            correlation_id,
        )
        result = await self.generator.generate(user_text, route.model)
        message = self.store.add_message(conversation_id, MessageRole.ASSISTANT, result.text)
        message.claims = result.claims
        await self.events.publish(
            session_id,
            "assistant.final",
            {
                "message_id": str(message.id),
                "content": message.content,
                "provenance": [claim.provenance for claim in message.claims],
            },
            correlation_id,
        )
        return message

