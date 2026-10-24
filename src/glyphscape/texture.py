"""Per-cell local-detail sampling: decides where glyphs land and how dense
they are, independent of chafa (which only supplies per-cell color)."""

from __future__ import annotations

from PIL import Image


def sample_cell_variance(image: Image.Image, cols: int, rows: int, cell: tuple[int, int]):
    """Local luminance standard deviation per cell -- a proxy for 'how much
    is happening here' (edges, texture) that chafa's own symbol choice
    isn't used for in this pipeline."""
    gray = image.convert("L")
    cw, ch = cell
    out = [[0.0] * cols for _ in range(rows)]
    px = gray.load()
    w, h = gray.size
    for r in range(rows):
        y0, y1 = r * ch, min((r + 1) * ch, h)
        for c in range(cols):
            x0, x1 = c * cw, min((c + 1) * cw, w)
            vals = [px[x, y] for y in range(y0, y1, 2) for x in range(x0, x1, 2)]
            if not vals:
                continue
            mean = sum(vals) / len(vals)
            out[r][c] = (sum((v - mean) ** 2 for v in vals) / len(vals)) ** 0.5
    return out
