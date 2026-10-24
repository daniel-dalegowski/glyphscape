"""Atomic PNG publishing: gnome-shell must never see a partial file."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PIL import Image


def atomic_write_png(image: Image.Image, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".png.tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            image.save(f, "PNG")
        os.replace(tmp_path, dest)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def write_meta(meta: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(meta, indent=2))


def _atomic_write_text(text: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dest.parent, suffix=".txt.tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(text)
        os.replace(tmp_path, dest)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def write_source_text(meta: dict, dest: Path) -> None:
    """Human-readable sidecar next to the wallpaper, so the image's source
    is a quick `cat` away rather than buried in the journal or meta.json."""
    lines = [
        f"Glyphscape — {meta.get('date', '')}",
        f"Title: {meta.get('title', '')}",
    ]
    if meta.get("location"):
        lines.append(f"Location: {meta['location']}")
    if meta.get("credit"):
        lines.append(f"Credit: {meta['credit']}")
    if meta.get("caption"):
        lines.append(f"Caption: {meta['caption']}")
    lines.append(f"Source URL: {meta.get('source_url', '')}")
    lines.append(f"Fetched via: {meta.get('source', '')}")
    _atomic_write_text("\n".join(lines) + "\n", dest)
