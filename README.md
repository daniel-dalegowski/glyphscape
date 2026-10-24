# Glyphscape

Once a day, fetch a photo of a beautiful place and render it as a circular
medallion of colored glyphs on a black GNOME wallpaper — Thai, Khmer,
Myanmar, Sinhala, Chinese, Braille, and round punctuation marks, chosen by
local image detail and colored from a fixed 18-color palette (Caves of
Qud's) with dithering. Infrastructure (fetch, scheduling, packaging) follows
the original design brief, `ASCII-daily-wallpaper-spec.md`; the rendering
itself moved well past that spec's literal "chafa ASCII art with a caption"
through iteration, which is also why the project is no longer named after
ASCII — see below.

## How a wallpaper gets built

1. **Fetch** — query the configured sources in priority order for today's
   image; first success wins (`sources.py` registry).
2. **Color** — run chafa once (`ascii` symbols, full truecolor) purely to
   get a representative (foreground, background) color per grid cell.
   Its own symbol/character choice is discarded — chafa has no concept of
   non-Latin scripts, so it's not useful for picking glyphs here.
3. **Glyph selection** — independently of chafa, sample local luminance
   variance per cell (`texture.py`) as a proxy for "how much detail is
   here." Candidate glyphs from the configured script set(s) are measured
   for their own ink density (rendered once, pixels counted) and binned by
   that density; each cell's variance picks a density bin, then a glyph is
   drawn from it — weighted by which script, with recent-repeat
   suppression so flat regions don't tile one character (`glyphsets.py`).
4. **Color grading** — the chosen ink color (chafa's cell color) is
   quantized to the configured fixed palette with Floyd-Steinberg dithering
   across the cell grid, so flat color patches become woven texture instead
   of solid blocks (`palette.py`).
5. **Framing** — a circle masks everything outside it to true black. Its
   vertical position is auto-searched for the strongest light/dark split
   inside it (sky meeting land reads far better than a flat crop); if even
   the best position is low-contrast, the density curve eases back so a
   genuinely flat/misty photo doesn't just vanish (`framing.py`).
6. **Rasterize & publish** — draw to a PNG at native resolution, write it
   atomically, and drop a plain-text sidecar (`live-source.txt`) with the
   image's title/credit/source URL — `glyphscape source` prints it, or
   just `cat` the file; it's also logged at INFO level on every publish.

## Status / scope

- **Sources**: Bing and Wikimedia Commons POTD fetch real data over the
  network; `local` is the offline fallback. Unsplash/NASA APOD are not
  implemented (need API keys) — see `sources/__init__.py`'s registry to add
  one.
- **Captions**: the original spec's in-grid caption stamping is not wired
  up to this pipeline — `caption.mode` only accepts `off`. The
  circular/glyph-set approach it would need to integrate with didn't exist
  when that code was written; folding it back in is open work.
- **Nix/home-manager module**: `nix build .#default` succeeds and the
  resulting `glyphscape` binary runs; `nix/package.nix`'s private fontconfig
  (`makeFontsConf` over `noto-fonts-cjk-sans`, `noto-fonts`, and
  `dejavu_fonts`) correctly resolves all five scripts (`fc-match` under
  `FONTCONFIG_FILE` finds `Noto Sans {CJK SC,Thai,Myanmar,Sinhala,Khmer}` as
  expected, no DejaVu fallback). The home-manager module itself (systemd
  timer, wallpaper registration) is still unexercised end-to-end on a real
  GNOME session. The Python pipeline was fully tested directly in this
  container, including a real Bing fetch through the complete render →
  publish → `prev`/`next` path.
- **GNOME reload on atomic rename**: still unverified (no GNOME session
  here). Fallback if it doesn't pick up the `mv`: toggle
  `picture-uri`/`picture-uri-dark` via `gsettings` between two filenames.

## Installation (NixOS / home-manager)

Add this to **your own** system or home-manager flake — not this repo's
`flake.nix` (that one already exists here and just defines the package/module
being consumed below):

```nix
# your flake.nix, e.g. /etc/nixos/flake.nix or your dotfiles' flake.nix
{
  inputs.glyphscape.url = "github:daniel-dalegowski/glyphscape";

  outputs = { home-manager, glyphscape, ... }: {
    homeConfigurations.you = home-manager.lib.homeManagerConfiguration {
      modules = [
        glyphscape.homeManagerModules.default
        {
          programs.glyphscape.enable = true;
          # programs.glyphscape.settings = { ... };  # see Configuration below
        }
      ];
    };
  };
}
```

This installs the `glyphscape` CLI, writes `~/.config/glyphscape/config.toml`,
registers the wallpaper in `~/.local/share/gnome-background-properties/`, and
sets up `systemd --user` timer `glyphscape.timer` (daily, catches up after
sleep, plus a run ~2min after login). Pick **Glyphscape** once in
Settings → Appearance.

### Without a flake (classic `configuration.nix` / `home.nix`)

`nix/module.nix` is a plain home-manager module — it doesn't need to come
through a flake input. If your system is set up the traditional
(channel-based) way, with `home-manager.users.<you> = import ./home.nix;` in
`configuration.nix`, just import it by path in `home.nix`:

```nix
{ config, pkgs, ... }:
{
  imports = [ /path/to/glyphscape/nix/module.nix ];

  programs.glyphscape.enable = true;
  # programs.glyphscape.settings = { ... };  # see Configuration below
}
```

Then `sudo nixos-rebuild switch` as usual — no separate `home-manager switch`
needed, since home-manager is wired in as a NixOS module here.

## Manual commands

```
glyphscape                  # daily entry point; no-ops if today is already rendered
glyphscape now               # force a fresh fetch + render, even if today is done
glyphscape render <image>    # render any local image, bypassing fetch — for testing
glyphscape render <image> --publish   # ...and set it as the live wallpaper
glyphscape prev / next       # step through the archive without re-fetching
glyphscape source             # print today's image title/credit/source URL
```

## Configuration

`~/.config/glyphscape/config.toml`, generated from `programs.glyphscape.settings`
on NixOS, or hand-edited otherwise.

| Key | Default | Meaning |
|---|---|---|
| `sources` | `["bing", "wikimedia", "local"]` | priority order, first success wins |
| `resolution` | `auto` | output size, e.g. `"2560x1600"` |
| `cell` | `"10x18"` | pixel size of one glyph cell |
| `dark_variant` | `true` | also render `live-dark.png` |
| `keep_days` | `30` | archive retention |
| `local_folder` | `~/Pictures/glyphscape` | offline fallback source folder |
| `color` | `"full"` | legacy chafa color remap, only used when `palette = "none"` |
| `palette` | `"qud"` | `"qud"` (18-color Caves of Qud palette, dithered) or `"none"` |
| `glyph.script` | `"mixed"` | `cjk`/`khmer`/`thai`/`myanmar`/`sinhala`/`braille`/`symbols`/`mixed` |
| `glyph.include_symbols` | `true` | blend round dots/bullets/asterisks into every script's density bins |
| `glyph.weights` | `{}` | per-script sampling weight overrides (e.g. `{braille = 0.1}`) |
| `glyph.density_gamma` | `1.5` | `level ** gamma`; >1 widens quiet/blank regions |
| `glyph.max_horizontal_run` | `2` | resample rather than repeat one glyph >N times in a row |
| `glyph.blank_floor` | `0.06` | cells below this normalized detail are candidates to stay blank |
| `glyph.glyph_color` | `"bg"` | which of chafa's two per-cell colors becomes the glyph ink |
| `circle.enabled` | `true` | mask everything outside a circle to black |
| `circle.radius` | `0.75` | fraction of `min(width,height)/2` |
| `circle.feather` | `0.0` | `0` = hard edge; `>0` = soft vignette fade at the rim |
| `circle.auto_contrast` | `true` | search vertical placement for the strongest light/dark split |
| `caption.mode` | `"off"` | only `off` is implemented against this pipeline (see Status) |

## Development / testing without Nix or GNOME

```
pip install -e .
export XDG_CONFIG_HOME=~/.config-test   # keep test state out of your real config
export XDG_CACHE_HOME=~/.cache-test
export XDG_DATA_HOME=~/.local/share-test
glyphscape render some-photo.jpg       # writes ./glyphscape-preview.png
```

Needs `chafa` and fontconfig-visible Noto Sans CJK SC / Khmer / Thai /
Myanmar / Sinhala and DejaVu Sans (`fc-match "Noto Sans Khmer"` etc. should
resolve) — on Debian/Ubuntu: `apt install chafa fonts-noto-cjk fonts-noto-core
fonts-dejavu-core`. `glyphsets.py`'s `SCRIPTS` dict is also where you'd point
a script at a literal font file path instead of a fontconfig family name.
