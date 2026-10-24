"""Bing image of the day (unofficial JSON endpoint, no key)."""

from __future__ import annotations

import re
from pathlib import Path

import requests

from .base import SourceError, USER_AGENT, download

ARCHIVE_URL = "https://www.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=en-US"
COPYRIGHT_RE = re.compile(r"^(?P<title>.*?)\s*\(©\s*(?P<credit>.*?)\)\s*$")


def fetch(session: requests.Session, workdir: Path) -> tuple[Path, dict]:
    resp = session.get(ARCHIVE_URL, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    images = data.get("images") or []
    if not images:
        raise SourceError("bing: no images in response")
    image = images[0]

    urlbase = image.get("urlbase")
    if not urlbase:
        raise SourceError("bing: missing urlbase")
    base_url = "https://www.bing.com" + urlbase

    dest = workdir / "source.jpg"
    for suffix in ("_UHD.jpg", "_1920x1080.jpg"):
        try:
            download(base_url + suffix, dest)
            break
        except (requests.RequestException, SourceError):
            continue
    else:
        raise SourceError("bing: could not download any resolution variant")

    copyright_text = image.get("copyright", "")
    match = COPYRIGHT_RE.match(copyright_text)
    if match:
        title = match.group("title")
        credit = match.group("credit")
    else:
        title = copyright_text or image.get("title", "Unknown location")
        credit = ""

    link = image.get("copyrightlink", "https://www.bing.com")
    meta = {
        "title": title,
        "location": "",
        "caption": image.get("title", title),
        "credit": credit,
        "source_url": link,
        "source": "bing",
    }
    return dest, meta
