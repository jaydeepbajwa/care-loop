"""Structured JSON logging.

One JSON object per line on stdout — the shape Datadog's agent ingests
directly (reserved attributes: `status`, `message`, `logger.name`).
"""

import json
import logging
import sys
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(UTC).isoformat(),
            "status": record.levelname,
            "logger": {"name": record.name},
            "message": record.getMessage(),
        }
        # Anything passed via `extra={"ctx": {...}}` lands as top-level fields,
        # so log pipelines can facet on them without parsing the message.
        ctx = getattr(record, "ctx", None)
        if ctx:
            entry.update(ctx)
        if record.exc_info and record.exc_info[0] is not None:
            entry["error"] = {
                "kind": record.exc_info[0].__name__,
                "stack": self.formatException(record.exc_info),
            }
        return json.dumps(entry, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn's access log duplicates our request middleware log — silence it
    logging.getLogger("uvicorn.access").disabled = True
