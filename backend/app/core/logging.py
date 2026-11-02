import json
import logging
import sys
from typing import Any, Dict, Optional


class JSONFormatter(logging.Formatter):
    """Formats log records as structured JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "task_id") and record.task_id:
            log_payload["task_id"] = record.task_id
        if hasattr(record, "agent_id") and record.agent_id:
            log_payload["agent_id"] = record.agent_id
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_payload)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configures root logger with structured JSON output."""
    root_logger = logging.getLogger("pixel_corp")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)
    return root_logger


logger = setup_logging()
