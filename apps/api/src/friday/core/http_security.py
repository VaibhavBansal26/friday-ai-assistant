from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class HttpSecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, maximum_body_bytes: int = 2_000_000):
        super().__init__(app)
        self.maximum_body_bytes = maximum_body_bytes

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("x-correlation-id") or str(uuid4())
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > self.maximum_body_bytes:
                    return self._error(413, "request_too_large", "Request body is too large", correlation_id)
            except ValueError:
                return self._error(400, "invalid_content_length", "Invalid content length", correlation_id)
        try:
            response = await call_next(request)
        except Exception:
            response = self._error(
                500,
                "internal_error",
                "An internal error occurred",
                correlation_id,
            )
        response.headers["x-correlation-id"] = correlation_id
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["x-frame-options"] = "DENY"
        response.headers["referrer-policy"] = "no-referrer"
        response.headers["cache-control"] = "no-store"
        return response

    @staticmethod
    def _error(status: int, code: str, message: str, correlation_id: str) -> JSONResponse:
        response = JSONResponse(
            status_code=status,
            content={
                "code": code,
                "message": message,
                "retryable": status >= 500,
                "correlation_id": correlation_id,
            },
        )
        response.headers["x-correlation-id"] = correlation_id
        response.headers["cache-control"] = "no-store"
        return response

