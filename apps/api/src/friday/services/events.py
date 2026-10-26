import asyncio
from collections import defaultdict
from uuid import UUID, uuid4

from friday.domain.models import EventEnvelope


class EventHub:
    """Process-local event transport; Redis Streams is the production adapter."""

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[EventEnvelope]]] = defaultdict(set)
        self._sequence: dict[UUID, int] = defaultdict(int)

    def subscribe(self, session_id: UUID) -> asyncio.Queue[EventEnvelope]:
        queue: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=100)
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: UUID, queue: asyncio.Queue[EventEnvelope]) -> None:
        self._subscribers[session_id].discard(queue)
        if not self._subscribers[session_id]:
            self._subscribers.pop(session_id, None)

    async def publish(
        self,
        session_id: UUID,
        event_type: str,
        payload: dict,
        correlation_id: UUID | None = None,
    ) -> EventEnvelope:
        self._sequence[session_id] += 1
        envelope = EventEnvelope(
            event_type=event_type,
            session_id=session_id,
            sequence=self._sequence[session_id],
            correlation_id=correlation_id or uuid4(),
            payload=payload,
        )
        for queue in self._subscribers.get(session_id, set()):
            if queue.full():
                _ = queue.get_nowait()
            queue.put_nowait(envelope)
        return envelope


event_hub = EventHub()

