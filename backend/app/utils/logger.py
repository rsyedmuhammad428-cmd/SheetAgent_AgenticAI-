"""
Logger — Phase 5
Structured JSON logging via structlog.
Writes to:
  - stdout (always)
  - workspace/logs/sheetagent.log (file, rotating)
"""
import structlog
import logging
import logging.handlers
from pathlib import Path
from app.config import settings


def setup_logging():
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # File handler — rotating, 10MB per file, 5 backups
    log_dir = settings.workspace_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "sheetagent.log"

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setLevel(log_level)

    # Configure stdlib logging
    logging.basicConfig(
        level=log_level,
        handlers=[logging.StreamHandler(), file_handler],
        format="%(message)s",
    )

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
            if settings.is_production
            else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
