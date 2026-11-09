"""Resolve screen resolution and compute the chafa grid size."""

from __future__ import annotations

import json
import logging
import re
import subprocess

log = logging.getLogger("glyphscape")

FALLBACK_RESOLUTION = (1920, 1080)
XRANDR_MODE_RE = re.compile(r"^\s*(\d+)x(\d+)\b.*\*")


def _detect_resolution_mutter() -> tuple[int, int] | None:
    """Ask Mutter's own DisplayConfig for the primary monitor's actual
    current mode. Needed because `xrandr` talks to Xwayland's compatibility
    stub under a Wayland session, which reports each output's EDID-preferred
    mode as "current" rather than what Mutter is really driving it at --
    e.g. a laptop panel's native 3072x1728 even when Mutter has it (and an
    external monitor) running at a shared 1920x1080."""
    try:
        out = subprocess.run(
            [
                "busctl", "--user", "call", "org.gnome.Mutter.DisplayConfig",
                "/org/gnome/Mutter/DisplayConfig", "org.gnome.Mutter.DisplayConfig",
                "GetCurrentState", "--json=short",
            ],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        _serial, monitors, logical_monitors, _props = json.loads(out)["data"]

        primary_connector = None
        for _x, _y, _scale, _transform, is_primary, connectors, _props in logical_monitors:
            if is_primary:
                primary_connector = connectors[0][0]
                break
        if primary_connector is None:
            return None

        for (connector, *_ids), modes, _props in monitors:
            if connector != primary_connector:
                continue
            for _mode_id, width, height, *_rest, mode_props in modes:
                if mode_props.get("is-current", {}).get("data"):
                    return width, height
        return None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, ValueError, IndexError):
        return None


def _detect_resolution_xrandr() -> tuple[int, int] | None:
    try:
        out = subprocess.run(
            ["xrandr", "--current"], capture_output=True, text=True, timeout=5, check=True
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None

    for line in out.splitlines():
        match = XRANDR_MODE_RE.match(line)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def detect_resolution() -> tuple[int, int]:
    resolution = _detect_resolution_mutter()
    if resolution is not None:
        return resolution

    resolution = _detect_resolution_xrandr()
    if resolution is not None:
        log.warning("Mutter DisplayConfig unavailable, falling back to xrandr")
        return resolution

    log.warning("could not detect screen resolution, falling back to %sx%s", *FALLBACK_RESOLUTION)
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
