"""Glyph sets: which scripts/fonts feed the density-ramp renderer.

Characters are picked by LOCAL IMAGE DETAIL (see texture.py), not by chafa's
own symbol selection -- chafa is used only for per-cell color (convert.py).
Each script contributes a pool of candidate codepoints; glyph_density()
renders each candidate once to measure how much "ink" it has, and only
codepoints the font's own cmap actually contains are considered. A font
missing a glyph renders a nonzero-density ".notdef" tofu box instead of
nothing, which silently corrupts a naive "does it look blank" check -- so
candidates are filtered against the font's real cmap (fontTools) first.
"""

from __future__ import annotations

import functools
import logging
import random
import shutil
import subprocess
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import ImageDraw, ImageFont, Image

log = logging.getLogger("glyphscape")

ROUND_SYMBOL_CHARS = ".·∘○◦•●∙*✦✧°⚬◍◎❋✺✱✲⁘:,"

# `font` is either a literal path ("...ttf"), a literal path with a
# collection index ("...ttc#2"), or a fontconfig family pattern resolved at
# runtime via fc-match (e.g. "Noto Sans Khmer"). The Nix module should pass
# literal store paths for full declarativeness; fc-match patterns are handy
# for local/dev testing against whatever fonts are installed.
SCRIPTS = {
    "cjk": {
        "font": "Noto Sans CJK SC",
        "calib": "国",
        "codepoints": list(range(0x4E00, 0x9FA0, 61)),
    },
    "khmer": {
        "font": "Noto Sans Khmer",
        "calib": "ក",
        "codepoints": (
            list(range(0x1780, 0x17A3)) + list(range(0x17A5, 0x17B4)) + list(range(0x17E0, 0x17EA))
        ),
    },
    "thai": {
        "font": "Noto Sans Thai",
        "calib": "ก",
        "codepoints": (
            list(range(0x0E01, 0x0E2F)) + list(range(0x0E30, 0x0E3B)) + list(range(0x0E40, 0x0E5A))
        ),
    },
    "myanmar": {
        "font": "Noto Sans Myanmar",
        "calib": "ဂ",
        "codepoints": list(range(0x1000, 0x102B)) + list(range(0x1040, 0x104A)),
    },
    "sinhala": {
        "font": "Noto Sans Sinhala",
        "calib": "ක",
        "codepoints": (
            list(range(0x0D85, 0x0D97)) + list(range(0x0D9A, 0x0DC7)) + list(range(0x0DE6, 0x0DF0))
        ),
    },
    "braille": {
        "font": "DejaVu Sans",
        "calib": "⣿",
        "codepoints": list(range(0x2800, 0x2900)),
    },
    "symbols": {
        "font": "DejaVu Sans",
        "calib": "●",
        "codepoints": [ord(c) for c in ROUND_SYMBOL_CHARS],
    },
}

MIXED_SCRIPT_KEYS = ["cjk", "khmer", "thai", "myanmar", "sinhala", "braille"]

DEFAULT_WEIGHTS = {
    "cjk": 1.0,
    "khmer": 1.0,
    "thai": 1.0,
    "myanmar": 1.0,
    "sinhala": 1.0,
    "braille": 0.35,  # toned down -- a 256-glyph pool otherwise dominates
    "symbols": 0.6,
    "blank": 2.5,  # how readily the sparsest bin stays empty vs. getting a mark
}


@functools.lru_cache(maxsize=16)
def resolve_font(spec: str) -> tuple[str, int]:
    """spec -> (file_path, collection_index)."""
    if "#" in spec:
        maybe_path, _, idx = spec.rpartition("#")
        if idx.isdigit() and Path(maybe_path).suffix.lower() in (".ttf", ".otf", ".ttc"):
            return maybe_path, int(idx)
    if spec.lower().endswith((".ttf", ".otf", ".ttc")):
        return spec, 0
    if shutil.which("fc-match"):
        out = subprocess.run(
            ["fc-match", "-f", "%{file}|%{index}", spec],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        path, _, idx = out.partition("|")
        if path:
            # fontconfig packs a variable-font named-instance index into the
            # high bits for formats like .ttc (e.g. 262146 = instance 4, face
            # 2); fontTools' fontNumber only wants the low 16 bits (the
            # actual TTC face index).
            return path, int(idx or 0) & 0xFFFF
    raise FileNotFoundError(f"could not resolve font {spec!r} (no fc-match, and not a file path)")


@functools.lru_cache(maxsize=8)
def _cmap(font_path: str, font_index: int) -> frozenset:
    tt = TTFont(font_path, fontNumber=font_index)
    cmap = frozenset(tt.getBestCmap().keys())
    tt.close()
    return cmap


def glyph_density(font: ImageFont.FreeTypeFont, char: str, size: int = 64) -> float:
    img = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(img)
    draw.text((size / 2, size / 2), char, font=font, fill=255, anchor="mm")
    pixels = img.tobytes()
    return sum(pixels) / len(pixels)


def resolve_pools(script: str, include_symbols: bool) -> list[tuple[str, dict]]:
    keys = list(MIXED_SCRIPT_KEYS) if script == "mixed" else [script]
    pools = [(k, SCRIPTS[k]) for k in keys]
    if include_symbols and "symbols" not in keys:
        pools.append(("symbols", SCRIPTS["symbols"]))
    return pools


def build_binned_pools(pools_with_keys: list[tuple[str, dict]], num_bins: int = 20):
    """Returns bins: list[dict[pool_key -> [(char, font_path, font_index), ...]]],
    bucketed by measured glyph density, lowest first."""
    font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
    scored = []
    for key, pool in pools_with_keys:
        font_path, font_index = resolve_font(pool["font"])
        fkey = (font_path, font_index)
        if fkey not in font_cache:
            font_cache[fkey] = ImageFont.truetype(font_path, 64, index=font_index)
        font = font_cache[fkey]
        cmap = _cmap(font_path, font_index)
        for cp in pool["codepoints"]:
            if cp not in cmap:
                continue
            ch = chr(cp)
            d = glyph_density(font, ch)
            if d > 2:
                scored.append((d, ch, font_path, font_index, key))

    if not scored:
        raise RuntimeError("no glyphs resolved for the configured script set")

    densities = [s[0] for s in scored]
    dmin, dmax = min(densities), max(densities)
    span = (dmax - dmin) or 1.0

    bins = [dict() for _ in range(num_bins)]
    for d, ch, fp, fi, key in scored:
        idx = min(num_bins - 1, int((d - dmin) / span * num_bins))
        bins[idx].setdefault(key, []).append((ch, fp, fi))
    return bins


def _nearest_nonempty_bin(bins: list[dict], idx: int) -> int:
    if bins[idx]:
        return idx
    for radius in range(1, len(bins)):
        for cand in (idx - radius, idx + radius):
            if 0 <= cand < len(bins) and bins[cand]:
                return cand
    return idx


def pick_glyph(
    bins: list[dict],
    bin_idx: int,
    weights: dict[str, float],
    rng: random.Random,
    avoid_chars: set[str],
    max_tries: int = 6,
):
    bin_idx = _nearest_nonempty_bin(bins, bin_idx)
    bin_data = bins[bin_idx]
    keys = list(bin_data.keys())
    w = [weights.get(k, 1.0) for k in keys]

    best = None
    for _ in range(max_tries):
        key = rng.choices(keys, weights=w, k=1)[0]
        ch, fp, fi = rng.choice(bin_data[key])
        if ch not in avoid_chars:
            return ch, fp, fi
        best = (ch, fp, fi)
    return best


class FontBook:
    """Caches correctly-sized font objects per (path, index), calibrated so
    each font's own representative glyph fills the cell width."""

    def __init__(self, cell: tuple[int, int], calibration: dict[tuple[str, int], str]):
        self.cell = cell
        self.calibration = calibration
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def get(self, font_path: str, font_index: int) -> ImageFont.FreeTypeFont:
        key = (font_path, font_index)
        if key not in self._cache:
            trial = ImageFont.truetype(font_path, self.cell[1], index=font_index)
            calib_char = self.calibration.get(key, "#")
            measured = trial.getlength(calib_char) or self.cell[0]
            size = max(1, round(self.cell[1] * self.cell[0] / measured))
            self._cache[key] = ImageFont.truetype(font_path, size, index=font_index)
        return self._cache[key]


def calibration_for(pools_with_keys: list[tuple[str, dict]]) -> dict[tuple[str, int], str]:
    calib = {}
    for _, pool in pools_with_keys:
        font_path, font_index = resolve_font(pool["font"])
        calib[(font_path, font_index)] = pool["calib"]
    return calib
