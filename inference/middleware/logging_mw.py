import time
import uuid
import logging
import json
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("inference")


def configure_logging(level: str = "INFO") -> None:
    """JSON structured logging."""

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            log_obj = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                log_obj["exception"] = self.formatException(record.exc_info)
            for key in ("request_id", "method", "path", "status_code", "duration_ms"):
                if hasattr(record, key):
                    log_obj[key] = getattr(record, key)
            return json.dumps(log_obj)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.monotonic()

        # attach request_id so downstream code can log it
        request.state.request_id = request_id

        response = await call_next(request)

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        extra = {
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        }
        logger.info("request completed", extra=extra)

        response.headers["X-Request-ID"] = request_id
        return response
