"""XDG-ish paths used throughout the pipeline."""

from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    return Path(os.environ.get("HOME", str(Path.home())))


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME", str(home() / ".config"))
    return Path(base) / "glyphscape"


def config_file() -> Path:
    return config_dir() / "config.toml"


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME", str(home() / ".cache"))
    return Path(base) / "glyphscape"


def day_dir(day: str) -> Path:
    return cache_dir() / day


def pointer_file() -> Path:
    return cache_dir() / "pointer.txt"


def data_dir() -> Path:
    base = os.environ.get("XDG_DATA_HOME", str(home() / ".local" / "share"))
    return Path(base) / "backgrounds" / "glyphscape"


def live_png() -> Path:
    return data_dir() / "live.png"


def live_dark_png() -> Path:
    return data_dir() / "live-dark.png"


def live_source_txt() -> Path:
    return data_dir() / "live-source.txt"
