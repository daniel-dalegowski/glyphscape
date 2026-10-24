"""Load ~/.config/glyphscape/config.toml, merged over defaults."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field

from . import paths

DEFAULTS = {
    "sources": ["bing", "wikimedia", "local"],
    "resolution": "auto",
    "cell": "10x18",
    "dark_variant": True,
    "keep_days": 30,
    "local_folder": "~/Pictures/glyphscape",
    "color": "full",
    "palette": "qud",
    "glyph": {
        "script": "mixed",
        "include_symbols": True,
        "weights": {},
        "bins": 20,
        "max_horizontal_run": 2,
        "blank_floor": 0.06,
        "density_gamma": 1.5,
        "glyph_color": "bg",
        "seed": 0,
    },
    "circle": {
        "enabled": True,
        "radius": 0.75,
        "feather": 0.0,
        "auto_contrast": True,
    },
    "caption": {
        "mode": "off",
        "lines": "name+credit",
    },
}


@dataclass
class Config:
    sources: list
    resolution: str
    cell: str
    dark_variant: bool
    keep_days: int
    local_folder: str
    color: str
    palette: str
    glyph_script: str
    glyph_include_symbols: bool
    glyph_weights: dict
    glyph_bins: int
    glyph_max_horizontal_run: int
    glyph_blank_floor: float
    glyph_density_gamma: float
    glyph_color_source: str
    glyph_seed: int
    circle_enabled: bool
    circle_radius: float
    circle_feather: float
    circle_auto_contrast: bool
    caption_mode: str
    caption_lines: str
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def cell_wh(self) -> tuple[int, int]:
        w, h = self.cell.lower().split("x")
        return int(w), int(h)


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load() -> Config:
    data = dict(DEFAULTS)
    cfg_path = paths.config_file()
    if cfg_path.exists():
        with cfg_path.open("rb") as f:
            user_data = tomllib.load(f)
        data = _deep_merge(data, user_data)

    glyph = data.get("glyph", {})
    circle = data.get("circle", {})
    caption = data.get("caption", {})

    return Config(
        sources=list(data["sources"]),
        resolution=str(data["resolution"]),
        cell=str(data["cell"]),
        dark_variant=bool(data["dark_variant"]),
        keep_days=int(data["keep_days"]),
        local_folder=str(data["local_folder"]),
        color=str(data["color"]),
        palette=str(data["palette"]),
        glyph_script=str(glyph.get("script", DEFAULTS["glyph"]["script"])),
        glyph_include_symbols=bool(glyph.get("include_symbols", DEFAULTS["glyph"]["include_symbols"])),
        glyph_weights=dict(glyph.get("weights", {})),
        glyph_bins=int(glyph.get("bins", DEFAULTS["glyph"]["bins"])),
        glyph_max_horizontal_run=int(
            glyph.get("max_horizontal_run", DEFAULTS["glyph"]["max_horizontal_run"])
        ),
        glyph_blank_floor=float(glyph.get("blank_floor", DEFAULTS["glyph"]["blank_floor"])),
        glyph_density_gamma=float(glyph.get("density_gamma", DEFAULTS["glyph"]["density_gamma"])),
        glyph_color_source=str(glyph.get("glyph_color", DEFAULTS["glyph"]["glyph_color"])),
        glyph_seed=int(glyph.get("seed", DEFAULTS["glyph"]["seed"])),
        circle_enabled=bool(circle.get("enabled", DEFAULTS["circle"]["enabled"])),
        circle_radius=float(circle.get("radius", DEFAULTS["circle"]["radius"])),
        circle_feather=float(circle.get("feather", DEFAULTS["circle"]["feather"])),
        circle_auto_contrast=bool(circle.get("auto_contrast", DEFAULTS["circle"]["auto_contrast"])),
        caption_mode=str(caption.get("mode", DEFAULTS["caption"]["mode"])),
        caption_lines=str(caption.get("lines", DEFAULTS["caption"]["lines"])),
        raw=data,
    )
