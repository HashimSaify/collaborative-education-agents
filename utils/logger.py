"""
utils/logger.py
---------------
Centralised logging configuration for the education agents system.
Provides a consistent log format, log rotation, and easy access via
get_logger() from anywhere in the codebase.
"""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config import LOG_LEVEL, LOG_FILE


# ── Formatter ─────────────────────────────────────────────────────────────────
_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

# ── Track whether logging has already been set up ────────────────────────────
_initialised = False


def setup_logger() -> None:
    """
    Configures the root logger once:
      - Rotating file handler (max 5 MB × 3 backups)
      - Stream handler (stdout)
    Should be called once at application startup (main.py / demo.py).
    """
    global _initialised
    if _initialised:
        return

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # ── File handler ──────────────────────────────────────────────────────────
    try:
        file_handler = RotatingFileHandler(
            filename=LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(_formatter)
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    except OSError as exc:
        print(f"[WARNING] Could not create log file at {LOG_FILE}: {exc}")

    # ── Console (stdout) handler ──────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(_formatter)
    # Show only WARNING and above on console to keep CLI output clean;
    # everything goes to the file.
    console_handler.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)

    # Silence noisy third-party loggers
    for noisy_lib in ("httpx", "httpcore", "openai", "crewai"):
        logging.getLogger(noisy_lib).setLevel(logging.WARNING)

    _initialised = True


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger.  setup_logger() must be called before using this.

    Usage:
        logger = get_logger(__name__)
        logger.info("Agent started")
    """
    return logging.getLogger(name)
