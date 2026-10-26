"""
Structured JSON Logging & Correlation ID Tracing.
Formats logs as structured JSON for ingestion into Splunk, CloudWatch, or Azure Monitor.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }

        # Include custom correlation attributes if present
        for attr in ("request_id", "client_ip", "path", "method", "status_code", "latency_ms", "user_id"):
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures the root application logger with JSON formatting."""
    logger = logging.getLogger("production_rag")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers = []

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger

logger = setup_logging()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Assigns or preserves an X-Request-ID header on every request for distributed tracing.
    Calculates execution duration and logs structured request metrics.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = req_id
        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Response-Time-MS"] = str(duration_ms)

        # Log request summary
        logger.info(
            f"{request.method} {request.url.path} - {response.status_code} ({duration_ms}ms)",
            extra={
                "request_id": req_id,
                "client_ip": request.client.host if request.client else "unknown",
                "path": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "latency_ms": duration_ms
            }
        )

        return response
