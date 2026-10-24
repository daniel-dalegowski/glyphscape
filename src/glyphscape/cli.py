"""Entry point: `glyphscape [now|prev|next|render <path>]`."""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

from . import archive, config as config_mod, paths, pipeline, publish
from .sources.base import validate_and_normalize

log = logging.getLogger("glyphscape")


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _cmd_run(config, force: bool) -> int:
    ok = pipeline.run_daily(config, force=force)
    return 0 if ok else 1


def _cmd_render(args, config) -> int:
    src_path = Path(args.image).expanduser()
    if not src_path.is_file():
        log.error("no such file: %s", src_path)
        return 1

    from . import grid

    resolution = grid.parse_resolution(config.resolution)

    with tempfile.TemporaryDirectory(prefix="glyphscape-render-") as tmp:
        work_copy = Path(tmp) / f"source{src_path.suffix or '.jpg'}"
        shutil.copyfile(src_path, work_copy)
        try:
            validate_and_normalize(work_copy, resolution)
        except Exception as exc:
            log.error("could not use %s: %s", src_path, exc)
            return 1

        meta = {
            "title": src_path.stem.replace("_", " ").replace("-", " ").title(),
            "location": "",
            "caption": "",
            "credit": "local test render",
            "source_url": "",
            "source": "render",
        }
        img, img_dark = pipeline.render_image(work_copy, meta, config)

    out = Path(args.out) if args.out else Path.cwd() / "glyphscape-preview.png"
    publish.atomic_write_png(img, out)
    log.info("wrote %s", out)
    if img_dark is not None:
        dark_out = out.with_name(out.stem + "-dark" + out.suffix)
        publish.atomic_write_png(img_dark, dark_out)
        log.info("wrote %s", dark_out)

    if args.publish:
        publish.atomic_write_png(img, paths.live_png())
        if img_dark is not None:
            publish.atomic_write_png(img_dark, paths.live_dark_png())
        meta["date"] = ""
        publish.write_source_text(meta, paths.live_source_txt())
        log.info("published to %s", paths.live_png())
    return 0


def _cmd_source(args, config) -> int:
    txt_path = paths.live_source_txt()
    if not txt_path.exists():
        log.error("no source info yet (nothing published)")
        return 1
    print(txt_path.read_text(), end="")
    return 0


def _cmd_step(args, config, direction: int) -> int:
    days = archive.finished_days()
    if not days:
        log.error("no archived renders yet")
        return 1

    pointer_path = paths.pointer_file()
    current = pointer_path.read_text().strip() if pointer_path.exists() else days[-1]
    try:
        idx = days.index(current)
    except ValueError:
        idx = len(days) - 1

    new_idx = max(0, min(len(days) - 1, idx + direction))
    day = days[new_idx]
    day_dir = paths.day_dir(day)

    publish.atomic_write_png(Image.open(day_dir / "live.png"), paths.live_png())
    dark_src = day_dir / "live-dark.png"
    if dark_src.exists():
        publish.atomic_write_png(Image.open(dark_src), paths.live_dark_png())
    source_src = day_dir / "source.txt"
    if source_src.exists():
        paths.live_source_txt().write_text(source_src.read_text())

    pointer_path.write_text(day)
    log.info("switched wallpaper to %s", day)
    return 0


def main(argv=None) -> int:
    _setup_logging()
    parser = argparse.ArgumentParser(prog="glyphscape")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("now", help="force a fresh fetch and render today")

    render_parser = sub.add_parser("render", help="render a local image without fetching")
    render_parser.add_argument("image")
    render_parser.add_argument("--out", help="output PNG path (default ./glyphscape-preview.png)")
    render_parser.add_argument("--publish", action="store_true", help="also set as the live wallpaper")

    sub.add_parser("prev", help="step to the previous archived wallpaper")
    sub.add_parser("next", help="step to the next archived wallpaper")
    sub.add_parser("source", help="print the current wallpaper's source info")

    args = parser.parse_args(argv)
    config = config_mod.load()

    if args.command == "now":
        return _cmd_run(config, force=True)
    if args.command == "render":
        return _cmd_render(args, config)
    if args.command == "prev":
        return _cmd_step(args, config, -1)
    if args.command == "next":
        return _cmd_step(args, config, +1)
    if args.command == "source":
        return _cmd_source(args, config)

    return _cmd_run(config, force=False)


if __name__ == "__main__":
    sys.exit(main())
