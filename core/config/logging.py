"""Central logging configuration for the UML Harness core."""

import logging
import os


class WorkflowFormatter(logging.Formatter):
    """Render workflow correlation fields in the development console."""

    _fields = (
        "thread_id",
        "diagram_type",
        "reflection_round",
        "clarification_round",
        "diagnostic_count",
        "error_count",
        "elapsed_ms",
        "revision_id",
    )

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        fields = {
            name: getattr(record, name)
            for name in self._fields
            if hasattr(record, name)
        }
        return f"{message} {fields}" if fields else message


class _WorkflowStreamHandler(logging.StreamHandler):
    """Mark the handler so repeated configuration remains idempotent."""

    _uml_harness_handler = True


def configure_logging() -> None:
    """Configure the core logger once without changing third-party loggers."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logger = logging.getLogger("core")
    logger.setLevel(level)
    logger.propagate = False
    if any(
        getattr(handler, "_uml_harness_handler", False) for handler in logger.handlers
    ):
        return
    handler = _WorkflowStreamHandler()
    handler.setLevel(level)
    handler.setFormatter(
        WorkflowFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    logger.addHandler(handler)
