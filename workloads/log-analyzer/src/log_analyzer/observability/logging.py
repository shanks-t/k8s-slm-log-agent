"""Structured logging with OpenTelemetry trace context injection."""

import logging
import json
from typing import Any
from opentelemetry import trace


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter that automatically injects trace context into logs.

    This enables correlation between logs and traces:
    - Logs include trace_id and span_id
    - Loki can extract trace_id to create links to Tempo
    - Tempo can query Loki for logs with matching trace_id
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON with trace context."""
        # Get current span context
        span = trace.get_current_span()
        span_context = span.get_span_context()

        # Build structured log entry
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Inject trace context if available
        if span_context.is_valid:
            log_data["trace_id"] = format(span_context.trace_id, "032x")
            log_data["span_id"] = format(span_context.span_id, "016x")
            log_data["trace_flags"] = span_context.trace_flags

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add any extra fields from logger.info("msg", extra={"key": "value"})
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


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
