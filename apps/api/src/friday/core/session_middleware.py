from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from friday.core.config import get_settings
from friday.services.local_auth import local_session_auth


PUBLIC_PATHS = {"/v1/health", "/v1/ready", "/v1/sessions", "/docs", "/openapi.json"}


class LocalSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not get_settings().require_local_session or request.url.path in PUBLIC_PATHS:
            return await call_next(request)
        session_value = request.headers.get("x-friday-session")
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        try:
            session_id = UUID(session_value) if session_value else None
        except ValueError:
            session_id = None
        if session_id is None or not token or not local_session_auth.verify(session_id, token):
            return JSONResponse(
                status_code=401,
                content={
                    "code": "invalid_local_session",
                    "message": "A valid local Friday session is required",
                    "retryable": False,
                },
            )
        return await call_next(request)

