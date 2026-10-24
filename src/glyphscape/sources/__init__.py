"""Source registry and fallback orchestration."""

from __future__ import annotations

import logging
from pathlib import Path

import requests

from . import bing, local, wikimedia
from .base import SourceError, validate_and_normalize

log = logging.getLogger("glyphscape")

_REGISTRY = {
    "bing": lambda session, workdir, config: bing.fetch(session, workdir),
    "wikimedia": lambda session, workdir, config: wikimedia.fetch(session, workdir),
    "local": lambda session, workdir, config: local.fetch(session, workdir, config.local_folder),
}


def fetch_image(config, workdir: Path, resolution: tuple[int, int]) -> tuple[Path, dict, str] | None:
    """Try each configured source in order; return the first that yields a
    usable still image, normalized to the target aspect ratio. None if every
    source failed (caller should leave yesterday's wallpaper in place)."""
    session = requests.Session()
    for name in config.sources:
        fetcher = _REGISTRY.get(name)
        if fetcher is None:
            log.warning("unknown source %r in config, skipping", name)
            continue
        try:
            image_path, meta = fetcher(session, workdir, config)
            validate_and_normalize(image_path, resolution)
        except (SourceError, requests.RequestException, OSError, ValueError, KeyError) as exc:
            log.info("source %s failed: %s", name, exc)
            continue
        log.info("source %s succeeded", name)
        return image_path, meta, name
    return None
