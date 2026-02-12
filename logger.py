"""
Structured logging for AutoOrder.
Writes to console + daily rotating log file.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import config


def setup_logger(name: str = "AutoOrder") -> logging.Logger:
    """Create and return a configured logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # ── Formatter ────────────────────────────────────────────────
    fmt = logging.Formatter(
        fmt="%(asctime)s │ %(levelname)-8s │ %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ── Console handler ──────────────────────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(fmt)
    logger.addHandler(console)

    # ── File handler (daily log) ─────────────────────────────────
    if config.LOG_ENABLED:
        log_dir = Path(config.LOG_DIR)
        log_dir.mkdir(parents=True, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = log_dir / f"order_{today}.log"
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger


# Module-level singleton
log = setup_logger()
