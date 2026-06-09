"""Structured logging configuration.

Replaces the previous text-file logger (`p2_log.py`) with a stdlib `logging`-based
setup that:

- Emits JSON lines compatible with CloudWatch Logs Insights.
- Carries a `correlation_id` across all log lines of a single pipeline run.
- Respects log levels per module (no manual gating).

Usage:
    from pipeline.logging_setup import configure_logging, get_logger

    configure_logging(correlation_id="abc-123", level="INFO")
    log = get_logger(__name__)
    log.info("pipeline started", extra={"bucket": bucket_name, "region": region})

Design note (vs the previous LoggerAdapter approach):

    The earlier design used LoggerAdapter(extra={"correlation_id": _CORRELATION_ID}),
    which captured _CORRELATION_ID at adapter-creation time. Since adapters are
    typically created at module import (before configure_logging runs), the captured
    value was always the initial sentinel "unset". This is the classic Python adapter
    pitfall.

    The current design uses a logging.Filter that reads _CORRELATION_ID at format
    time, so reconfiguring the correlation_id after import takes effect for all
    subsequent log calls.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import UTC, datetime
from typing import Any

# Module-level state holding the current correlation ID. Read at log time
# (via CorrelationIdFilter) rather than at adapter creation time.
_CORRELATION_ID: str = "unset"


class CorrelationIdFilter(logging.Filter):
    """Inject the current correlation_id into every log record at format time."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current correlation_id to the record."""
        record.correlation_id = _CORRELATION_ID
        return True


class JsonFormatter(logging.Formatter):
    """Format log records as single-line JSON with structured fields."""

    # Standard LogRecord attributes that we never emit verbatim
    _STANDARD_ATTRS = frozenset(
        {
            "args",
            "asctime",
            "created",
            "exc_info",
            "exc_text",
            "filename",
            "funcName",
            "levelname",
            "levelno",
            "lineno",
            "message",
            "module",
            "msecs",
            "msg",
            "name",
            "pathname",
            "process",
            "processName",
            "relativeCreated",
            "stack_info",
            "thread",
            "threadName",
            "taskName",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        """Serialize the record as a single JSON line."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", _CORRELATION_ID),
        }

        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "traceback": self.formatException(record.exc_info),
            }

        # Merge any extras passed via `extra={"key": value}`
        for key, value in record.__dict__.items():
            if key in payload or key.startswith("_") or key in self._STANDARD_ATTRS:
                continue
            payload[key] = value

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    *,
    correlation_id: str | None = None,
    level: str = "INFO",
) -> str:
    """Set up JSON logging to stdout and return the active correlation_id.

    correlation_id is auto-generated when omitted. Idempotent: calling again
    replaces the handler instead of stacking a duplicate.
    """
    global _CORRELATION_ID  # noqa: PLW0603 - module-level config by design
    _CORRELATION_ID = correlation_id or str(uuid.uuid4())

    root = logging.getLogger()
    root.setLevel(level)

    # Remove existing handlers to avoid duplication on re-configure
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(JsonFormatter())
    stdout_handler.addFilter(CorrelationIdFilter())
    root.addHandler(stdout_handler)

    # Silence noisy third-party loggers
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("py4j").setLevel(logging.WARNING)

    return _CORRELATION_ID


def get_logger(name: str) -> logging.Logger:
    """Return a plain stdlib Logger.

    The CorrelationIdFilter from configure_logging injects correlation_id at
    log time, so callers never thread it through by hand.
    """
    return logging.getLogger(name)


def get_correlation_id() -> str:
    """Return the currently active correlation ID."""
    return _CORRELATION_ID
