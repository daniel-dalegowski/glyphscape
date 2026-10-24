# ASCII Daily Wallpaper — Spec

Oct 24, 2026 · @Daniel Dalegowski

## Overview

Once a day, fetch a photo of a beautiful place, convert it to colored ASCII/Unicode art with chafa, write the place's name and caption into the text scene, and render it as a GNOME wallpaper. Think Windows Spotlight, but as a terminal-art piece.

Goals:

- Appears in Settings → Appearance as a normal selectable wallpaper ("ASCII Daily").
- New image roughly once a day, with no manual steps.
- The caption is part of the art, set in the same character grid, not a separate overlay.
- Fully declarative on NixOS; no daemons beyond a systemd user timer.
- Degrades gracefully: offline or a bad fetch leaves yesterday's wallpaper in place.

## Pipeline

One script, `ascii-daily`, runs these steps in order. Each stage writes into a per-day work dir (`~/.cache/ascii-daily/YYYY-MM-DD/`) so any step can be rerun or debugged alone.

1. **Fetch** — query the configured source for today's image; save `source.jpg` plus `meta.json` (title, location, caption, credit, source URL).
2. **Size the grid** — compute columns × rows from the screen resolution and the chosen cell size (e.g. 2560×1600 at 8×16 px cells = 320 × 100). Reserve rows for the caption band.
3. **Convert** — run chafa on the image at exactly that grid, color output as ANSI (`chafa --format symbols --size 320x92 --symbols ascii --colors full`).
4. **Compose** — parse chafa's ANSI output into a grid of (char, fg, bg) cells; stamp the caption into the grid (see Caption placement).
5. **Rasterize** — draw the cell grid to a PNG at screen resolution with a monospace font.
6. **Publish** — write to a temp file, then atomically `mv` over `live.png` (and `live-dark.png` if enabled). gnome-shell sees the change and reloads.
7. **Archive** — keep the last N days' PNGs and metadata for browsing or a "previous" command.

## Image sources and fallback

Sources are pluggable: each is a small function returning an image URL plus metadata. The first configured source is primary; the rest are fallbacks tried in order.

| Source | Access | Caption data | Notes |
| --- | --- | --- | --- |
| Bing image of the day | Unofficial JSON endpoint, no key | Title + copyright line naming the place | Closest to Windows Spotlight; endpoint could change |
| Wikimedia Commons POTD | Public API, no key | Description + author | Freely licensed; subjects vary beyond landscapes |
| Unsplash | API key | Description, location, photographer | Can filter by topic (e.g. landscapes) |
| NASA APOD | API key (DEMO\_KEY works lightly) | Title + explanation | Skip days where media is video |
| Local folder | None | Filename or sidecar text | Offline fallback, also good for testing |

Rules:

- Skip anything that isn't a still image or is under a minimum resolution.
- Prefer landscape aspect; letterbox or crop portrait images to the screen ratio.
- If every source fails, do nothing: the previous wallpaper stays.

Open question: one source fixed, or rotate sources by day of week?

## Caption placement

The caption is written into the character grid itself, so it reads as part of the scene rather than a label on top.

**Content** — two lines: the place name (e.g. `MORAINE LAKE · BANFF, CANADA`) and a short secondary line (credit, or the first sentence of the description, truncated with `…`).

**Placement modes** (configurable):

- **Band** (default) — reserve 3–4 rows at the bottom; fill them with a dim solid or sparse texture and set the caption in it. Simplest and always legible.
- **Quiet region** — scan the grid for the calmest rectangle (lowest luminance variance) that fits the caption, avoiding the screen's top bar and the center where windows usually sit; carve it out and write there. Feels most "in the scene."
- **Box** — draw an ASCII frame (`+--+` / `|  |`) around the caption in a corner, like a terminal dialog.

**Legibility rules:**

- Caption cells get a forced background (darkened average of the cells they replace) and a high-contrast foreground.
- Clear a one-cell margin around the text so the art doesn't touch the letters.
- Name line in upper case or bold weight; secondary line in a dimmer color.
- Never place text under the GNOME top bar (first \~2 rows at 8×16 cells).

## Rendering and GNOME integration

**Rasterizer** — Python + Pillow. Parse chafa's ANSI (24-bit SGR codes) into cells, then for each cell fill the background rect and draw the glyph in its foreground color. A monospace TTF with a known cell size (e.g. JetBrains Mono, IBM Plex Mono, or a bitmap font like Terminus for a crisp look). Alternative if Pillow is awkward: `ansilove`, though it's tuned for classic BBS fonts.

**Output** — PNG at native screen resolution, no scaling by GNOME (`<options>zoom</options>` with an exact-size image is effectively 1:1). Optional `live-dark.png` with a darker palette.

**GNOME registration** — `~/.local/share/gnome-background-properties/ascii-daily.xml` with one `<wallpaper>` entry named "ASCII Daily" pointing at `~/.local/share/backgrounds/ascii-daily/live.png` (and `filename-dark`). The user picks it once in Settings → Appearance.

**Refresh** — gnome-shell watches the wallpaper file and reloads on change. Always write a temp file in the same directory and `mv` it over the target so the shell never reads a partial PNG. The Settings thumbnail won't update; that's cosmetic.

To verify: does atomic rename reliably trigger the reload on the current GNOME version? Test early; fallback is toggling `picture-uri` via `gsettings` between two filenames.

## Configuration options

One TOML file (`~/.config/ascii-daily/config.toml`), generated by home-manager.

| Key | Default | Meaning |
| --- | --- | --- |
| `sources` | `["bing", "wikimedia", "local"]` | Priority order of image sources |
| `resolution` | auto-detect | Output size, e.g. `2560x1600` |
| `cell` | `8x16` | Pixel size of one character cell; sets detail level |
| `symbols` | `ascii` | chafa symbol set: `ascii`, `block`, `braille`, `sextant`, … |
| `color` | `full` | `full`, `256`, `mono-green`, `mono-amber`, `grayscale` |
| `font` | JetBrains Mono | Monospace font used to rasterize |
| `caption.mode` | `band` | `band`, `quiet-region`, `box`, `off` |
| `caption.lines` | `name+credit` | What goes in the second line |
| `dark_variant` | `true` | Also render `live-dark.png` |
| `keep_days` | `30` | Archive retention |

The `mono-green` / `mono-amber` palettes give the CRT look: map luminance to one hue on black.

## Scheduling, packaging and failure handling

**Schedule** — systemd user timer, `OnCalendar=daily` plus `Persistent=true` so a laptop that was asleep at midnight catches up on wake. Add `OnStartupSec=2min` for a run shortly after login. The script exits early if today's work dir already has a finished PNG.

**Packaging (NixOS / home-manager)** — a small module providing:

- the script as a `writers.writePython3Bin` (or a tiny derivation) with `chafa`, `pillow`, `requests` and the font in its closure;
- `xdg.dataFile` for the background-properties XML;
- the config TOML from module options;
- `systemd.user.services.ascii-daily` + `systemd.user.timers.ascii-daily`.

**Manual commands** — `ascii-daily now` (force refresh), `ascii-daily prev` / `next` (step through the archive), `ascii-daily render <image>` (any local file, for testing).

**Failure handling** — network errors, bad JSON, non-image media, or render errors log to the journal and leave the current wallpaper untouched. No partial files ever replace `live.png`.

**Out of scope for v1** — interactive or animated wallpapers, a GNOME Shell extension, multi-monitor per-screen images, and an AI-written caption.

