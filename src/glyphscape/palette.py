"""Fixed color palettes with nearest-color quantization and optional
Floyd-Steinberg dithering across the glyph-cell grid (same algorithm as
pixel dithering, just diffusing error between cells instead of pixels --
this is what breaks a limited palette's flat same-color patches into a
woven texture instead of solid blocks)."""

from __future__ import annotations

from .compose import luminance

# Caves of Qud's 18 fixed colors, verified against
# wiki.cavesofqud.com/wiki/Modding:Colors_%26_Object_Rendering (2026-10-24).
QUD_PALETTE_NAMED = {
    "r": "#a64a2e", "R": "#d74200", "o": "#f15f22", "O": "#e99f10",
    "w": "#98875f", "W": "#cfc041", "g": "#009403", "G": "#00c420",
    "b": "#0048bd", "B": "#0096ff", "c": "#40a4b9", "C": "#77bfcf",
    "m": "#b154cf", "M": "#da5bd6", "k": "#0f3b3a", "K": "#155352",
    "y": "#b1c9c3", "Y": "#ffffff",
}


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


QUD_PALETTE = [_hex_to_rgb(v) for v in QUD_PALETTE_NAMED.values()]
PALETTES = {"qud": QUD_PALETTE}


def darkest_color(palette: list) -> tuple[int, int, int]:
    """Lowest-luminance entry in a palette -- used for background = "palette"
    so the backdrop always harmonizes with that palette's ink colors. No
    per-palette curation needed, but a palette with no genuinely dark color
    (e.g. a light theme) will still return its darkest-available entry,
    which may not read as "dark" at all."""
    return min(palette, key=luminance)


def nearest_color(rgb, palette: list) -> tuple[int, int, int]:
    best, best_d = palette[0], None
    for p in palette:
        d = (rgb[0] - p[0]) ** 2 + (rgb[1] - p[1]) ** 2 + (rgb[2] - p[2]) ** 2
        if best_d is None or d < best_d:
            best_d, best = d, p
    return best


def quantize(color_grid: list[list], palette: list, dither: bool = True) -> list[list]:
    rows = len(color_grid)
    cols = len(color_grid[0]) if rows else 0
    work = [[list(c) for c in row] for row in color_grid]
    out = [[None] * cols for _ in range(rows)]
    for r in range(rows):
        for c in range(cols):
            old = work[r][c]
            new = nearest_color(old, palette)
            out[r][c] = new
            if not dither:
                continue
            err = [old[i] - new[i] for i in range(3)]
            if c + 1 < cols:
                for i in range(3):
                    work[r][c + 1][i] += err[i] * 7 / 16
            if r + 1 < rows:
                if c - 1 >= 0:
                    for i in range(3):
                        work[r + 1][c - 1][i] += err[i] * 3 / 16
                for i in range(3):
                    work[r + 1][c][i] += err[i] * 5 / 16
                if c + 1 < cols:
                    for i in range(3):
                        work[r + 1][c + 1][i] += err[i] * 1 / 16
    return out
