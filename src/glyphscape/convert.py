"""Run chafa and parse its 24-bit ANSI output into a (char, fg, bg) grid."""

from __future__ import annotations

import re
import subprocess
from collections import namedtuple
from pathlib import Path

Cell = namedtuple("Cell", "char fg bg")

BLANK_FG = (200, 200, 200)
BLANK_BG = (0, 0, 0)

_ESCAPE_RE = re.compile(r"\x1b\[([?0-9;]*)([A-Za-z])")


def run_chafa(image_path: Path, cols: int, rows: int, symbols: str, colors: str) -> str:
    cmd = [
        "chafa",
        "--format",
        "symbols",
        f"--size={cols}x{rows}",
        "--stretch",  # fill the exact grid; we already cropped to the target aspect ratio
        f"--symbols={symbols}",
        f"--colors={colors}",
        "--",
        str(image_path),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=60, check=True)
    return result.stdout.decode("utf-8", errors="replace")


def _parse_line(line: str, cols: int) -> list[Cell]:
    cells: list[Cell] = []
    fg, bg = BLANK_FG, BLANK_BG
    pos = 0
    for match in _ESCAPE_RE.finditer(line):
        # Any plain characters since the last escape belong to the current (fg, bg).
        literal = line[pos : match.start()]
        for ch in literal:
            cells.append(Cell(ch, fg, bg))
        pos = match.end()

        params, final = match.groups()
        if final != "m" or params.startswith("?"):
            continue
        tokens = params.split(";") if params else ["0"]
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok in ("", "0"):
                fg, bg = BLANK_FG, BLANK_BG
                i += 1
            elif tok in ("38", "48"):
                sub = tokens[i + 1] if i + 1 < len(tokens) else ""
                if sub == "2" and i + 4 < len(tokens):
                    color = (int(tokens[i + 2]), int(tokens[i + 3]), int(tokens[i + 4]))
                    if tok == "38":
                        fg = color
                    else:
                        bg = color
                    i += 5
                elif sub == "5" and i + 2 < len(tokens):
                    color = _xterm256_to_rgb(int(tokens[i + 2]))
                    if tok == "38":
                        fg = color
                    else:
                        bg = color
                    i += 3
                else:
                    i += 1
            else:
                i += 1

    # Trailing literal characters after the last escape sequence.
    for ch in line[pos:]:
        cells.append(Cell(ch, fg, bg))

    if len(cells) < cols:
        cells.extend(Cell(" ", BLANK_FG, BLANK_BG) for _ in range(cols - len(cells)))
    return cells[:cols]


def _xterm256_to_rgb(index: int) -> tuple[int, int, int]:
    if index < 16:
        grayscale_or_basic = [
            (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
            (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
            (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
            (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
        ]
        return grayscale_or_basic[index]
    if index < 232:
        index -= 16
        levels = (0, 95, 135, 175, 215, 255)
        r, g, b = index // 36, (index % 36) // 6, index % 6
        return levels[r], levels[g], levels[b]
    gray = 8 + (index - 232) * 10
    return gray, gray, gray


def parse_ansi(text: str, cols: int, rows: int) -> list[list[Cell]]:
    lines = text.split("\n")
    # Drop empty trailing lines left by chafa's final newline / cursor-show code.
    while lines and _ESCAPE_RE.sub("", lines[-1]).strip() == "":
        lines.pop()

    grid = [_parse_line(line, cols) for line in lines[:rows]]
    while len(grid) < rows:
        grid.append([Cell(" ", BLANK_FG, BLANK_BG) for _ in range(cols)])
    return grid
