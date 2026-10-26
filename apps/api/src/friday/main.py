from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from friday.api.routes import router
from friday.core.http_security import HttpSecurityMiddleware
from friday.core.session_middleware import LocalSessionMiddleware
from friday.services.events import event_hub
from friday.services.store import store

app = FastAPI(
    title="Friday API",
    version="0.1.0",
    description="Safety-first local gateway for the Friday desktop assistant.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT"],
    allow_headers=["content-type", "x-friday-session", "authorization"],
)
app.add_middleware(HttpSecurityMiddleware)
app.add_middleware(LocalSessionMiddleware)
app.include_router(router)


@app.websocket("/v1/sessions/{session_id}/events")
async def session_events(websocket: WebSocket, session_id: UUID) -> None:
    if session_id not in store.sessions:
        await websocket.close(code=4404, reason="Session not found")
        return
    await websocket.accept()
    queue = event_hub.subscribe(session_id)
    try:
        await websocket.send_json(
            (
                await event_hub.publish(
                    session_id,
                    "execution.stage",
                    {"stage": "connected", "label": "Friday is ready"},
                )
            ).model_dump(mode="json")
        )
        while True:
            event = await queue.get()
            if event.event_type != "execution.stage" or event.payload.get("stage") != "connected":
                await websocket.send_json(event.model_dump(mode="json"))
    except WebSocketDisconnect:
        pass
    finally:
        event_hub.unsubscribe(session_id, queue)
