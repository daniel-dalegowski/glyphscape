"""Shared helpers for image sources: fetching, validation, normalization."""

from __future__ import annotations

import logging
from pathlib import Path

import requests
from PIL import Image, UnidentifiedImageError

log = logging.getLogger("glyphscape")

MIN_WIDTH = 1280
MIN_HEIGHT = 720
USER_AGENT = "glyphscape/0.1 (https://github.com/; personal wallpaper script)"


class SourceError(Exception):
    """Raised by a source when it has no usable image today."""


def download(url: str, dest: Path, timeout: float = 20.0) -> None:
    headers = {"User-Agent": USER_AGENT}
    with requests.get(url, headers=headers, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        if content_type and not content_type.startswith("image/"):
            raise SourceError(f"not an image: content-type {content_type!r}")
        with dest.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)


def validate_and_normalize(image_path: Path, target_resolution: tuple[int, int]) -> None:
    """Reject undersized/non-image files; crop or letterbox in place to match
    the screen's aspect ratio so the downstream chafa grid fills cleanly."""
    try:
        with Image.open(image_path) as im:
            im.load()
            width, height = im.size
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                raise SourceError(f"image too small: {width}x{height}")

            target_w, target_h = target_resolution
            target_ratio = target_w / target_h
            ratio = width / height

            rgb = im.convert("RGB")
            if ratio < target_ratio * 0.9:
                # Portrait-ish: letterbox onto a black canvas at the target ratio.
                canvas_h = height
                canvas_w = round(canvas_h * target_ratio)
                canvas = Image.new("RGB", (canvas_w, canvas_h), (0, 0, 0))
                canvas.paste(rgb, ((canvas_w - width) // 2, 0))
                out = canvas
            else:
                # Landscape (or close enough): center-crop to the target ratio.
                if ratio > target_ratio:
                    new_w = round(height * target_ratio)
                    left = (width - new_w) // 2
                    out = rgb.crop((left, 0, left + new_w, height))
                else:
                    new_h = round(width / target_ratio)
                    top = (height - new_h) // 2
                    out = rgb.crop((0, top, width, top + new_h))
            out.save(image_path, "JPEG", quality=92)
    except UnidentifiedImageError as exc:
        raise SourceError(f"not a still image: {exc}") from exc
