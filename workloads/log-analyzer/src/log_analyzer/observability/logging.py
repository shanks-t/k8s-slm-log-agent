"""Structured logging with OpenTelemetry trace context injection."""

import logging
import json
from typing import Any, TypedDict
from opentelemetry import trace


STANDARD_LOG_RECORD_ATTRS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
}


class StructuredLog(TypedDict, total=False):
    timestamp: str
    level: str
    logger: str
    message: str

    trace_id: str
    span_id: str
    sampled: bool

    exception: str


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter that automatically injects trace context into logs.

    For OTel the recommended production approach:
    - Use standard logging
    - Inject trace context manually or via instrumentation
    - Emit structured logs (JSON) for systems like Loki

    This enables correlation between logs and traces:
    - Logs include trace_id and span_id
    - Loki can extract trace_id to create links to Tempo
    - Tempo can query Loki for logs with matching trace_id
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with trace context."""
        # Get current span context
        span = trace.get_current_span()
        if span is not None:
            span_context = span.get_span_context()
            # Build structured log entry
            log_data: dict[str, Any] = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # there are legitimate cases where there is no active span
            # logging should never break in these cases so we skip injection
            if span_context.is_valid:
                log_data["trace_id"] = format(span_context.trace_id, "032x")
                log_data["span_id"] = format(span_context.span_id, "016x")
                log_data["sampled"] = bool(span_context.trace_flags & 0x01)

            # Add exception info if present
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)

            # Add any extra fields from logger.info("msg", extra={"key": "value"})
            for key, value in record.__dict__.items():
                if key not in STANDARD_LOG_RECORD_ATTRS:
                    log_data[key] = value
        else:
            # Fallback to standard log format if no span
            log_data = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if record.exc_info:
                log_data["exception"] = self.formatException(record.exc_info)
            for key, value in record.__dict__.items():
                if key not in STANDARD_LOG_RECORD_ATTRS:
                    log_data[key] = value
        # cast for clarity (no runtime affect)
        # suppress only assignment related mypy errors
        structured_log: StructuredLog = log_data  # type: ignore[assignment]
        return json.dumps(structured_log)


def setup_logging(level: str = "INFO"):
    """
    Configure structured logging with trace context injection.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(level)

    # Remove existing handlers
    # no duplicates, avoids mixed formatting, makes logs deterministic
    # NOTE: if other libraries have added handlers, this removes them too
    logger.handlers.clear()

    # Create console handler with structured formatter
    handler = logging.StreamHandler()
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a module.

    Usage:
        logger = get_logger(__name__)
        logger.info("Processing logs", extra={"extra_fields": {"count": 10}})

    Args:
        name: Logger name (typically __name__)

    Returns:
        Logger instance with trace context injection
    """
    return logging.getLogger(name)
