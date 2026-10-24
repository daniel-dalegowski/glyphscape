"""Color-mode post-processing and caption stamping (quiet-region placement)."""

from __future__ import annotations

from .convert import Cell

TOP_BAR_PX = 32  # GNOME's top bar height; row count to avoid scales with cell_h.
EDGE_MARGIN = 1
CAPTION_INNER_MARGIN = 1

NAME_FG_LIGHT = (245, 245, 245)
NAME_FG_DARK = (15, 15, 15)
CREDIT_DIM_FACTOR = 0.6
CAPTION_BG_DARKEN = 0.45


def luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def apply_color_mode(grid: list[list[Cell]], mode: str) -> list[list[Cell]]:
    """chafa is always run with --colors=full; everything else about the
    'color' config knob is a remap we apply ourselves on the parsed grid."""
    if mode == "full":
        return grid
    if mode == "256":
        return [[Cell(c.char, _quantize(c.fg), _quantize(c.bg)) for c in row] for row in grid]
    if mode == "grayscale":
        return [[Cell(c.char, _gray(c.fg), _gray(c.bg)) for c in row] for row in grid]
    if mode in ("mono-green", "mono-amber"):
        hue = (80, 255, 90) if mode == "mono-green" else (255, 176, 60)
        return [[Cell(c.char, _tint(c.fg, hue), _tint(c.bg, hue)) for c in row] for row in grid]
    return grid


def _quantize(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    levels = (0, 95, 135, 175, 215, 255)

    def snap(v: int) -> int:
        return min(levels, key=lambda lv: abs(lv - v))

    return snap(rgb[0]), snap(rgb[1]), snap(rgb[2])


def _gray(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    g = round(luminance(rgb))
    return g, g, g


def _tint(rgb: tuple[int, int, int], hue: tuple[int, int, int]) -> tuple[int, int, int]:
    # Map luminance onto one hue on black, like a CRT amber/green monitor.
    level = luminance(rgb) / 255.0
    return tuple(round(h * level) for h in hue)


def _prefix_sums(values: list[list[float]], cols: int, rows: int) -> list[list[float]]:
    prefix = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for r in range(rows):
        for c in range(cols):
            prefix[r + 1][c + 1] = (
                prefix[r][c + 1] + prefix[r + 1][c] - prefix[r][c] + values[r][c]
            )
    return prefix


def _window_sum(prefix: list[list[float]], top: int, left: int, h: int, w: int) -> float:
    return (
        prefix[top + h][left + w]
        - prefix[top][left + w]
        - prefix[top + h][left]
        + prefix[top][left]
    )


def find_quiet_region(
    grid: list[list[Cell]], cols: int, rows: int, box_w: int, box_h: int, top_bar_rows: int
) -> tuple[int, int]:
    """Return (top, left) of the box_h x box_w window of lowest background
    luminance variance, avoiding the top bar and the center of the screen."""
    lum = [[luminance(grid[r][c].bg) for c in range(cols)] for r in range(rows)]
    lum_sq = [[v * v for v in row] for row in lum]
    sum_prefix = _prefix_sums(lum, cols, rows)
    sq_prefix = _prefix_sums(lum_sq, cols, rows)

    center_top, center_bottom = int(rows * 0.3), int(rows * 0.7)
    center_left, center_right = int(cols * 0.3), int(cols * 0.7)

    best = None
    best_variance = float("inf")
    n = box_w * box_h
    for top in range(top_bar_rows, rows - box_h - EDGE_MARGIN):
        for left in range(EDGE_MARGIN, cols - box_w - EDGE_MARGIN):
            bottom, right = top + box_h, left + box_w
            overlaps_center = (
                top < center_bottom and bottom > center_top
                and left < center_right and right > center_left
            )
            if overlaps_center:
                continue
            s = _window_sum(sum_prefix, top, left, box_h, box_w)
            sq = _window_sum(sq_prefix, top, left, box_h, box_w)
            mean = s / n
            variance = sq / n - mean * mean
            if variance < best_variance:
                best_variance = variance
                best = (top, left)

    if best is None:
        # Screen too small to avoid the center; fall back to the bottom band.
        return rows - box_h - EDGE_MARGIN, (cols - box_w) // 2
    return best


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max(max_len - 1, 0)] + "…"


def stamp_caption(
    grid: list[list[Cell]], cols: int, rows: int, name_line: str, credit_line: str, cell_h: int
) -> set[tuple[int, int]]:
    """Carve a legible box out of the grid for the caption and write the two
    lines into it. Returns the set of (row, col) cells the caption occupies,
    so the dark-variant render can treat them specially."""
    top_bar_rows = max(1, -(-TOP_BAR_PX // cell_h))  # ceil division

    max_text_len = min(max(cols - 2 * (EDGE_MARGIN + CAPTION_INNER_MARGIN), 10), 56)
    name_line = _truncate(name_line.upper(), max_text_len)
    credit_line = _truncate(credit_line, max_text_len)

    box_w = min(cols - 2 * EDGE_MARGIN, max(len(name_line), len(credit_line)) + 2 * CAPTION_INNER_MARGIN)
    box_h = min(rows - top_bar_rows - EDGE_MARGIN, 4)

    top, left = find_quiet_region(grid, cols, rows, box_w, box_h, top_bar_rows)

    # Average the original cells under the box, then darken for the backdrop.
    total = [0.0, 0.0, 0.0]
    count = 0
    for r in range(top, top + box_h):
        for c in range(left, left + box_w):
            bg = grid[r][c].bg
            total[0] += bg[0]
            total[1] += bg[1]
            total[2] += bg[2]
            count += 1
    avg_bg = tuple(v / count for v in total)
    backdrop = tuple(round(v * CAPTION_BG_DARKEN) for v in avg_bg)
    name_fg = NAME_FG_LIGHT if luminance(backdrop) < 128 else NAME_FG_DARK
    credit_fg = tuple(round(backdrop[i] + (name_fg[i] - backdrop[i]) * CREDIT_DIM_FACTOR) for i in range(3))

    touched: set[tuple[int, int]] = set()
    for r in range(top, top + box_h):
        for c in range(left, left + box_w):
            grid[r][c] = Cell(" ", name_fg, backdrop)
            touched.add((r, c))

    text_row_start = top + CAPTION_INNER_MARGIN
    name_row = text_row_start
    credit_row = text_row_start + 1
    text_col = left + CAPTION_INNER_MARGIN

    for i, ch in enumerate(name_line):
        grid[name_row][text_col + i] = Cell(ch, name_fg, backdrop)
    for i, ch in enumerate(credit_line):
        grid[credit_row][text_col + i] = Cell(ch, credit_fg, backdrop)

    return touched


def build_caption_lines(meta: dict, lines_mode: str) -> tuple[str, str]:
    name_parts = [p for p in (meta.get("title", ""), meta.get("location", "")) if p]
    name_line = " · ".join(name_parts) or "UNKNOWN"

    if lines_mode == "name+caption" and meta.get("caption"):
        credit_line = meta["caption"]
    else:
        credit_line = meta.get("credit", "") or meta.get("caption", "")
    return name_line, credit_line


def dim_grid(grid: list[list[Cell]], caption_cells: set[tuple[int, int]], factor: float = 0.55) -> list[list[Cell]]:
    out = []
    for r, row in enumerate(grid):
        new_row = []
        for c, cell in enumerate(row):
            if (r, c) in caption_cells:
                f = 0.85
            else:
                f = factor
            new_row.append(
                Cell(
                    cell.char,
                    tuple(round(v * f) for v in cell.fg),
                    tuple(round(v * f) for v in cell.bg),
                )
            )
        out.append(new_row)
    return out
