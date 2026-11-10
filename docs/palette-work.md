# Palette work log

Tracks the palette issues found in the 2026-11-07 review, their status, and
the decisions made along the way. Update this file as items move.

Status key: **done** · **in progress** · **deferred** · **open**

## Issues

| # | Issue | Status |
|---|---|---|
| 1 | Unknown `palette` name silently falls back to `"none"` | **done** |
| 2 | Dithering is hardwired on; no config switch | **done** |
| 3 | Dark variant dims inks *after* quantization, so `live-dark.png` is off-palette | **done** |
| 4 | Nearest-color match uses plain RGB distance, not a perceptual space | **deferred** |
| 5a | No user-defined palettes in config | **done** |
| 5b | No palette derived from the day's photo | **deferred** |
| 6 | Spec calls `mono-green`/`mono-amber` "palettes"; in code they're `color` modes | **done** |

### 1. Unknown palette name fails silently

Before: `pipeline.py` did `PALETTES.get(config.palette)`; any miss (typo
included) meant "no palette" with no warning.

Fix: `Config.active_palette` resolves the name and raises `ValueError` listing
the valid names. `cli.main` resolves it right after config load and `--set`
overrides, so a bad name exits immediately with a clear message instead of
mid-render.

### 2. Dithering not configurable

Fix: new top-level `dither` key (default `true`), also settable via
`--set dither=false`. Applies to both the normal and dark renders.

### 3. Dark variant off-palette

Before: dark render = final (quantized + feather-blended) ink × 0.55.

Fix: the dark render now dims the *pre-quantization* ink, then quantizes and
dithers that against the palette, then applies the circle feather blend. So
`live-dark.png` uses only palette colors (plus the feather fade toward the
background, same as the light render).

### 4. Perceptual color matching — deferred

Switching nearest-color to CIELAB (or OKLab) distance is a numerics change
that also affects how dithering error diffuses (error should arguably be
diffused in the same space). Per project rules (numerics → `architect`
first), this needs a short design pass before implementation. Expected
visible effect: fewer odd hue jumps (e.g. muted greens snapping to teal).

### 5a. User-defined palettes

Fix: new `[palettes]` table in config.toml, name → list of hex colors:

```toml
palette = "dusk"

[palettes]
dusk = ["#1b1b2f", "#162447", "#1f4068", "#e43f5a", "#f4d35e"]
```

### 5b. Photo-derived palette — deferred

E.g. `palette = "auto:8"` → k-means / median-cut the day's photo to N colors.
Deferred: it's a clustering/numerics feature (same `architect`-first rule as
#4), and it interacts with #4 (which color space to cluster in). Worth doing
after #4 lands.

### 6. Spec terminology

Fix: `Glyphscape-spec.md` now calls `mono-green`/`mono-amber` `color` modes
and points at `palette` for fixed palettes.

## Decisions

- **2026-11-07 — Custom palettes can't shadow built-ins or `"none"`.** Defining
  `[palettes] qud = [...]` is an error rather than an override, so `"qud"`
  always means the same thing in shared configs and bug reports. Pick a new
  name instead.
- **2026-11-07 — Bad palette config is a hard error, not a warning.** A typo
  previously produced a valid-looking but wrong wallpaper; failing loudly
  (the daily run keeps yesterday's wallpaper) is easier to notice in the
  journal than a subtly different render.
- **2026-11-07 — Dark variant re-quantizes from the source ink, not from the
  light render's quantized ink.** Dimming and re-matching already-quantized
  colors would double-quantize and give a blotchier result; dithering the
  dimmed original gives a proper dithered dark image.
- **2026-11-07 — Dark variant feather fades to the real background.** Side
  effect of #3: previously the dark render's feathered rim faded toward a
  dimmed background color (darker than the actual backdrop); now it fades
  into the backdrop itself, matching the light render. Only visible when
  `circle.feather > 0`.
- **2026-11-07 — `dither` is top-level, not `palette.dither`.** `palette` is
  already a string key; making it a table would break existing configs.
- **2026-11-07 — #4 and #5b deferred** for an `architect` design pass (see
  above).

## Known effects to watch

- With the Qud palette, the dark variant leans heavily on its few dark
  entries (`k #0f3b3a`, `K #155352`, `b`, `r`, `g`), so dark renders read as
  teal-tinted with dithered highlights. That is the palette being honest;
  if it looks wrong, the remedy is a palette with more dark steps, not
  going back to off-palette dimming.
  - Measured 2026-11-07 on the Bing "DakotaBison" image at 1280x720: light
    render uses 10 distinct Qud colors, dark render uses 2 (dark teal plus
    a rust red), 0 off-palette ink cells in either. Visually it's
    comparable in brightness to the old dark render, but flatter in hue.
    If that reads as too monotone day to day, options are a gentler dim
    factor for palette mode or a curated dark companion palette — not
    decided yet.

## Verification (2026-11-07)

- `--set palette=qdu` → exits 1 with `unknown palette 'qdu'; available: none, qud`.
- `[palettes] qud = [...]` → exits 1, can't redefine built-in.
- Malformed hex in a custom palette → exits 1 naming the palette.
- Custom `dusk` palette renders; `--set dither=false` renders.
- No automated test suite exists; checks were manual renders.
