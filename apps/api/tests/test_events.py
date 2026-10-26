from uuid import uuid4

import pytest

from friday.services.events import EventHub


@pytest.mark.asyncio
async def test_events_are_versioned_and_sequenced():
    hub = EventHub()
    session_id = uuid4()
    first = await hub.publish(session_id, "execution.stage", {"stage": "thinking"})
    second = await hub.publish(session_id, "execution.stage", {"stage": "acting"})
    assert first.version == "1"
    assert first.sequence == 1
    assert second.sequence == 2

