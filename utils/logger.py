"""
logger.py — simple rotating file logger for court_booker.

Usage:
    from logger import log

    log("Starting booking run")
    log("Selected slot: 6:00 PM - 7:00 PM", level="INFO")
    log("Save button not found", level="ERROR")

Log files are written to ./logs/court_booker_YYYY-MM-DD.log
Log files older than LOG_RETENTION_DAYS are deleted on each run.
"""

import os
import logging
from datetime import datetime, timedelta
import glob

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
LOG_RETENTION_DAYS = 30


def _get_logger() -> logging.Logger:
    """Build (or retrieve) the logger, creating today's log file if needed."""
    logger_name = "court_booker"
    logger = logging.getLogger(logger_name)

    # Only configure once per process
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    os.makedirs(LOG_DIR, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    log_path = os.path.join(LOG_DIR, f"court_booker_{today}.log")

    # File handler — append so multiple runs in a day accumulate
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)

    # Console handler — mirrors to stdout so you still see output live
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fmt)
    ch.setFormatter(fmt)

    logger.addHandler(fh)
    logger.addHandler(ch)

    _purge_old_logs()

    return logger


def _purge_old_logs():
    """Delete log files older than LOG_RETENTION_DAYS."""
    cutoff = datetime.now() - timedelta(days=LOG_RETENTION_DAYS)
    pattern = os.path.join(LOG_DIR, "court_booker_*.log")
    for path in glob.glob(pattern):
        fname = os.path.basename(path)
        # filename: court_booker_YYYY-MM-DD.log
        date_part = fname.replace("court_booker_", "").replace(".log", "")
        try:
            file_date = datetime.strptime(date_part, "%Y-%m-%d")
            if file_date < cutoff:
                os.remove(path)
                # Use print here — logger may not be fully wired yet
                print(f"[logger] Purged old log: {fname}")
        except ValueError:
            pass  # skip files that don't match the expected pattern


def log(message: str, level: str = "INFO"):
    """
    Write a message to today's log file and stdout.

    Args:
        message: The message to log.
        level:   One of DEBUG / INFO / WARNING / ERROR / CRITICAL (case-insensitive).
                 Defaults to INFO.
    """
    logger = _get_logger()
    method = getattr(logger, level.lower(), logger.info)
    method(message)
