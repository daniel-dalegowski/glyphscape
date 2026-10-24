"""Wikimedia Commons Picture of the Day (public API, no key)."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import requests

from .base import SourceError, USER_AGENT, download

API_URL = "https://commons.wikimedia.org/w/api.php"
TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return TAG_RE.sub("", text or "").strip()


def _api_get(session: requests.Session, **params) -> dict:
    params.setdefault("format", "json")
    resp = session.get(API_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def fetch(session: requests.Session, workdir: Path) -> tuple[Path, dict]:
    today = date.today().isoformat()
    template_title = f"Template:Potd/{today}"

    data = _api_get(session, action="query", titles=template_title, prop="images")
    pages = (data.get("query") or {}).get("pages") or {}
    page = next(iter(pages.values()), {})
    images = page.get("images") or []
    if not images:
        raise SourceError("wikimedia: no POTD listed for today")
    file_title = images[0]["title"]

    info = _api_get(
        session,
        action="query",
        titles=file_title,
        prop="imageinfo",
        iiprop="url|extmetadata",
    )
    info_pages = (info.get("query") or {}).get("pages") or {}
    info_page = next(iter(info_pages.values()), {})
    imageinfo = (info_page.get("imageinfo") or [{}])[0]
    url = imageinfo.get("url")
    if not url:
        raise SourceError("wikimedia: missing file url")

    meta_fields = imageinfo.get("extmetadata", {})
    description = _strip_html(meta_fields.get("ImageDescription", {}).get("value", ""))
    artist = _strip_html(meta_fields.get("Artist", {}).get("value", ""))
    object_name = _strip_html(meta_fields.get("ObjectName", {}).get("value", ""))

    dest = workdir / "source.jpg"
    download(url, dest)

    title = object_name or file_title.removeprefix("File:").rsplit(".", 1)[0]
    meta = {
        "title": title,
        "location": "",
        "caption": description,
        "credit": artist,
        "source_url": f"https://commons.wikimedia.org/wiki/{file_title.replace(' ', '_')}",
        "source": "wikimedia",
    }
    return dest, meta
