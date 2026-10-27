"""Orchestrates fetch -> size -> convert -> compose -> rasterize -> publish -> archive.

Rendering approach: chafa supplies per-cell COLOR only (run once, ascii
symbols, full truecolor); the glyph drawn in each cell comes from our own
density-ramp glyph sets (glyphsets.py) driven by local image detail
(texture.py), not by chafa's own symbol choice -- see glyphsets.py's
docstring for why (chafa has no concept of non-Latin scripts). Color is
then optionally quantized to a fixed palette with dithering (palette.py),
and the whole frame is masked to a circle (framing.py), auto-placed to
land a strong light/dark boundary inside it when possible.
"""

from __future__ import annotations

import logging
import random
from datetime import date
from pathlib import Path

from PIL import Image

from . import archive, compose, convert, framing, glyphsets, grid, palette as palette_mod
from . import paths, publish, rasterize, sources, texture

log = logging.getLogger("glyphscape")


def _dim(rgb: tuple[float, float, float], factor: float) -> tuple[float, float, float]:
    return tuple(v * factor for v in rgb)


def _blend_toward(
    rgb: tuple[float, float, float], bg: tuple[float, float, float], factor: float
) -> tuple[float, float, float]:
    """Fade ink toward bg as factor goes from 1 (full ink) to 0 (pure bg) --
    used for the circle's feathered edge so it fades into the configured
    background instead of always fading to black."""
    return tuple(v * factor + b * (1 - factor) for v, b in zip(rgb, bg))


def render_image(image_path: Path, meta: dict | None, config):
    resolution = grid.parse_resolution(config.resolution)
    cell = config.cell_wh
    sizing = grid.compute_grid(resolution, cell)
    cols, rows = sizing["cols"], sizing["rows"]
    mx, my = sizing["margin_x"], sizing["margin_y"]
    res_w, res_h = sizing["resolution"]

    # 1. Color: chafa's own symbol choice is discarded, only (fg, bg) per cell is kept.
    ansi = convert.run_chafa(image_path, cols, rows, "ascii", "full")
    cell_grid = convert.parse_ansi(ansi, cols, rows)

    active_palette = palette_mod.PALETTES.get(config.palette)
    if active_palette is None:
        # No fixed palette configured: fall back to the legacy full-color /
        # mono-green / mono-amber / grayscale remap.
        cell_grid = compose.apply_color_mode(cell_grid, config.color)

    # 2. Glyphs: pick by local detail, from the configured script set(s).
    pools = glyphsets.resolve_pools(config.glyph_script, config.glyph_include_symbols)
    bins = glyphsets.build_binned_pools(pools, num_bins=config.glyph_bins)
    calibration = glyphsets.calibration_for(pools)

    with Image.open(image_path) as src:
        src_for_variance = src.resize((cols * cell[0], rows * cell[1]))
        variance = texture.sample_cell_variance(src_for_variance, cols, rows, cell)
        src_for_contrast = src.resize((res_w, res_h)) if src.size != (res_w, res_h) else src.copy()
    vmax = max(max(row) for row in variance) or 1.0

    # 3. Circle framing: search for the vertical placement with the
    # strongest light/dark split, and ease density_gamma if even the best
    # placement is fairly flat (a misty/low-contrast photo shouldn't just
    # vanish under a gamma tuned for crisp landscapes).
    density_gamma = config.glyph_density_gamma
    circle_center = (res_w / 2, res_h / 2)
    max_r = None
    if config.circle_enabled:
        max_r = min(res_w, res_h) / 2 * config.circle_radius
        if config.circle_auto_contrast:
            circle_center, contrast_score = framing.find_best_circle_center(
                src_for_contrast, (res_w, res_h), config.circle_radius
            )
            density_gamma = framing.eased_density_gamma(density_gamma, contrast_score)
            log.info("circle center y=%.0f (contrast score %.1f)", circle_center[1], contrast_score)

    bg_rgb = config.background_rgb
    if bg_rgb is None:
        if config.background.strip().lower() == "palette" and active_palette:
            bg_rgb = palette_mod.darkest_color(active_palette)
            log.info("palette background color #%02x%02x%02x", *bg_rgb)
        else:
            bg_rgb = framing.auto_background_color(src_for_contrast)
            log.info("auto background color #%02x%02x%02x", *bg_rgb)

    weights = {**glyphsets.DEFAULT_WEIGHTS, **config.glyph_weights}
    rng = random.Random(config.glyph_seed)

    new_grid = []
    mask_grid = []
    for r in range(rows):
        row_history: list[str] = []
        new_row = []
        mask_row = []
        for c in range(cols):
            mask_val = 1.0
            if max_r is not None:
                px = mx + (c + 0.5) * cell[0]
                py = my + (r + 0.5) * cell[1]
                mask_val = framing.circle_mask_value(px, py, circle_center, max_r, config.circle_feather)

            level = variance[r][c] / vmax
            if density_gamma != 1.0:
                level = level**density_gamma
            old = cell_grid[r][c]

            if mask_val <= 0.0:
                ch, fp, fi = " ", None, 0
            elif level < config.glyph_blank_floor and rng.random() < weights.get("blank", 1.0) / (
                weights.get("blank", 1.0) + 1.0
            ):
                ch, fp, fi = " ", None, 0
            else:
                bin_idx = min(config.glyph_bins - 1, int(level * config.glyph_bins))
                run = config.glyph_max_horizontal_run
                avoid = set(row_history[-run:]) if run > 0 and len(row_history) >= run else set()
                ch, fp, fi = glyphsets.pick_glyph(bins, bin_idx, weights, rng, avoid)

            row_history.append(ch)
            new_row.append((ch, fp, fi, old.fg, old.bg))
            mask_row.append(mask_val)
        new_grid.append(new_row)
        mask_grid.append(mask_row)

    # 4. Ink color: chafa's fg or bg (per config), then palette quantize/dither.
    ink_grid = [
        [(bg if config.glyph_color_source == "bg" else fg) for (_, _, _, fg, bg) in row]
        for row in new_grid
    ]
    if active_palette:
        ink_grid = palette_mod.quantize(ink_grid, active_palette, dither=True)
    if max_r is not None:
        ink_grid = [
            [_blend_toward(ink_grid[r][c], bg_rgb, mask_grid[r][c]) for c in range(cols)]
            for r in range(rows)
        ]

    final_grid = [
        [(new_grid[r][c][0], new_grid[r][c][1], new_grid[r][c][2], ink_grid[r][c]) for c in range(cols)]
        for r in range(rows)
    ]

    caption_cells: set[tuple[int, int]] = set()
    if config.caption_mode not in ("off",) and meta:
        raise NotImplementedError(
            f"caption.mode={config.caption_mode!r} is not implemented against the "
            "circle/glyph-set pipeline yet; only 'off' is supported."
        )

    margin = (mx, my)
    img = rasterize.rasterize(
        final_grid, cell, (res_w, res_h), margin, calibration, bg_color=bg_rgb
    )

    img_dark = None
    if config.dark_variant:
        dark_grid = [
            [
                (ch, fp, fi, _dim(ink, 0.85 if (r, c) in caption_cells else 0.55))
                for c, (ch, fp, fi, ink) in enumerate(row)
            ]
            for r, row in enumerate(final_grid)
        ]
        img_dark = rasterize.rasterize(
            dark_grid, cell, (res_w, res_h), margin, calibration, bg_color=bg_rgb
        )

    return img, img_dark


def run_daily(config, force: bool = False) -> bool:
    today = date.today().isoformat()
    workdir = paths.day_dir(today)
    workdir.mkdir(parents=True, exist_ok=True)

    if not force and (workdir / "live.png").exists():
        log.info("today (%s) already has a finished render, skipping", today)
        return True

    resolution = grid.parse_resolution(config.resolution)
    result = sources.fetch_image(config, workdir, resolution)
    if result is None:
        log.error("every image source failed today; leaving current wallpaper in place")
        return False
    image_path, meta, source_name = result
    meta["date"] = today
    meta["source"] = source_name

    log.info(
        "source: %s | %s | credit: %s | %s",
        source_name, meta.get("title", ""), meta.get("credit", ""), meta.get("source_url", ""),
    )

    try:
        img, img_dark = render_image(image_path, meta, config)
    except Exception:
        log.exception("render failed; leaving current wallpaper in place")
        return False

    publish.atomic_write_png(img, paths.live_png())
    publish.atomic_write_png(img, workdir / "live.png")
    if img_dark is not None:
        publish.atomic_write_png(img_dark, paths.live_dark_png())
        publish.atomic_write_png(img_dark, workdir / "live-dark.png")
    publish.write_meta(meta, workdir / "meta.json")
    publish.write_source_text(meta, paths.live_source_txt())
    publish.write_source_text(meta, workdir / "source.txt")

    paths.pointer_file().write_text(today)
    archive.prune(config.keep_days)
    log.info("published wallpaper for %s (source=%s)", today, source_name)
    return True
