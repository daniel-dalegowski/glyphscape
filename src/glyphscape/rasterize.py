"""Draw the glyph grid to a PNG. Each cell may use a different font, since
the mixed-script glyph sets each need their own font file (see glyphsets.py)."""

from __future__ import annotations

from PIL import Image, ImageDraw

from .glyphsets import FontBook


def rasterize(
    cell_grid: list[list[tuple]],  # (char, font_path, font_index, ink_rgb) per cell
    cell: tuple[int, int],
    resolution: tuple[int, int],
    margin: tuple[int, int],
    calibration: dict[tuple[str, int], str],
    bg_grid: list[list] | None = None,  # optional per-cell fill; None = flat bg_color canvas
    bg_color: tuple[int, int, int] = (0, 0, 0),
) -> Image.Image:
    cell_w, cell_h = cell
    res_w, res_h = resolution
    margin_x, margin_y = margin
    rows = len(cell_grid)
    cols = len(cell_grid[0]) if rows else 0

    fonts = FontBook(cell, calibration)
    img = Image.new("RGB", (res_w, res_h), bg_color)
    draw = ImageDraw.Draw(img)

    for r in range(rows):
        y0 = margin_y + r * cell_h
        row = cell_grid[r]
        for c in range(cols):
            ch, fp, fi, ink = row[c]
            x0 = margin_x + c * cell_w
            if bg_grid is not None:
                draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], fill=bg_grid[r][c])
            if ch != " ":
                font = fonts.get(fp, fi)
                draw.text(
                    (x0 + cell_w / 2, y0 + cell_h / 2),
                    ch,
                    font=font,
                    fill=tuple(round(v) for v in ink),
                    anchor="mm",
                )
    return img
