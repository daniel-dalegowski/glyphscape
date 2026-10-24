"""Prune old per-day work dirs beyond the configured retention window."""

from __future__ import annotations

import logging
import shutil
from datetime import date, datetime

from . import paths

log = logging.getLogger("glyphscape")


def prune(keep_days: int) -> None:
    cache = paths.cache_dir()
    if not cache.is_dir():
        return

    today = date.today()
    for entry in cache.iterdir():
        if not entry.is_dir():
            continue
        try:
            day = datetime.strptime(entry.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if (today - day).days > keep_days:
            log.info("archive: pruning %s", entry)
            shutil.rmtree(entry, ignore_errors=True)


def finished_days() -> list[str]:
    """Day strings (sorted ascending) that have a completed render."""
    cache = paths.cache_dir()
    if not cache.is_dir():
        return []
    days = []
    for entry in cache.iterdir():
        if entry.is_dir() and (entry / "live.png").exists():
            try:
                datetime.strptime(entry.name, "%Y-%m-%d")
            except ValueError:
                continue
            days.append(entry.name)
    return sorted(days)
