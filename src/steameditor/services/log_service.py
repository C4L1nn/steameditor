"""steameditor.services.log_service — Structured logging with rotation."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from steameditor.services.config_service import get_config_service


def setup_logging() -> logging.Logger:
    """Configure application logging."""
    config_service = get_config_service()
    log_dir = config_service.config_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "steameditor.log"

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Clear existing handlers
    for h in root.handlers[:]:
        root.removeHandler(h)

    # File handler with rotation (1.5MB, keep 3)
    fh = RotatingFileHandler(log_file, maxBytes=512 * 1024, backupCount=2, encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    root.addHandler(fh)

    # Console handler (clean, no timestamps)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("%(message)s"))
    root.addHandler(ch)

    # Suppress noisy third-party loggers
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    return root


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a module."""
    return logging.getLogger(f"steameditor.{name}")