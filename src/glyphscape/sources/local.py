"""Local folder fallback: no network, used offline or for testing.

Cycles deterministically through whatever images are in the configured
folder, one per day of the year, so re-runs on the same day are stable.
"""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

import requests

from .base import SourceError

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}


def _load_sidecar(image_path: Path) -> dict:
    json_sidecar = image_path.with_suffix(".json")
    if json_sidecar.exists():
        try:
            return json.loads(json_sidecar.read_text())
        except (OSError, ValueError):
            pass

    txt_sidecar = image_path.with_suffix(".txt")
    if txt_sidecar.exists():
        lines = txt_sidecar.read_text().splitlines()
        title = lines[0].strip() if lines else ""
        caption = lines[1].strip() if len(lines) > 1 else ""
        return {"title": title, "caption": caption}

    return {}


def fetch(session: requests.Session, workdir: Path, folder: str) -> tuple[Path, dict]:
    folder_path = Path(folder).expanduser()
    if not folder_path.is_dir():
        raise SourceError(f"local: no such folder {folder_path}")

    images = sorted(p for p in folder_path.iterdir() if p.suffix.lower() in IMAGE_EXTS)
    if not images:
        raise SourceError(f"local: no images in {folder_path}")

    index = date.today().timetuple().tm_yday % len(images)
    chosen = images[index]

    dest = workdir / "source.jpg"
    shutil.copyfile(chosen, dest)

    sidecar = _load_sidecar(chosen)
    title = sidecar.get("title") or chosen.stem.replace("_", " ").replace("-", " ").title()
    meta = {
        "title": title,
        "location": sidecar.get("location", ""),
        "caption": sidecar.get("caption", ""),
        "credit": sidecar.get("credit", ""),
        "source_url": "",
        "source": "local",
    }
    return dest, meta
