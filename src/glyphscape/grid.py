"""Resolve screen resolution and compute the chafa grid size."""

from __future__ import annotations

import logging
import re
import subprocess

log = logging.getLogger("glyphscape")

FALLBACK_RESOLUTION = (1920, 1080)
XRANDR_MODE_RE = re.compile(r"^\s*(\d+)x(\d+)\b.*\*")


def detect_resolution() -> tuple[int, int]:
    try:
        out = subprocess.run(
            ["xrandr", "--current"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        log.warning("xrandr unavailable, falling back to %sx%s", *FALLBACK_RESOLUTION)
        return FALLBACK_RESOLUTION

    for line in out.splitlines():
        match = XRANDR_MODE_RE.match(line)
        if match:
            return int(match.group(1)), int(match.group(2))

    log.warning("could not find active mode in xrandr output, falling back to %sx%s", *FALLBACK_RESOLUTION)
    return FALLBACK_RESOLUTION


def parse_resolution(resolution: str) -> tuple[int, int]:
    if resolution.strip().lower() == "auto":
        return detect_resolution()
    w, h = resolution.lower().split("x")
    return int(w), int(h)


def compute_grid(resolution: tuple[int, int], cell: tuple[int, int]) -> dict:
    width, height = resolution
    cell_w, cell_h = cell
    cols = width // cell_w
    rows = height // cell_h
    used_w = cols * cell_w
    used_h = rows * cell_h
    return {
        "cols": cols,
        "rows": rows,
        "resolution": (width, height),
        "margin_x": (width - used_w) // 2,
        "margin_y": (height - used_h) // 2,
    }
