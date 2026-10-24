# Builds the `glyphscape` CLI with chafa on its PATH and a private
# fontconfig config pointing at exactly the fonts this package needs, so the
# glyph-set system (glyphsets.py, which resolves fonts by family name via
# `fc-match`) works reproducibly regardless of what fonts the user's own
# profile happens to have installed.
#
# UNVERIFIED: this derivation has not been built (no Nix in the dev
# environment this was written in). In particular, double-check:
#   - `noto-fonts-cjk-sans` and `noto-fonts` actually cover Thai/Myanmar/
#     Sinhala/Khmer in the nixpkgs version you're on (Debian's equivalent
#     split is fonts-noto-cjk + fonts-noto-core) -- `fc-list` inside a
#     `nix shell` with these packages is the fastest way to check.
#   - `makeFontsConf` is in scope at the top level of your nixpkgs (it has
#     moved around across versions); if not, build a fontconfig.conf by hand
#     with `<dir>` entries for each font package instead.
{
  lib,
  python3Packages,
  chafa,
  fontconfig,
  makeFontsConf,
  noto-fonts-cjk-sans,
  noto-fonts,
  dejavu_fonts,
}:

let
  fontsConf = makeFontsConf {
    fontDirectories = [
      noto-fonts-cjk-sans
      noto-fonts
      dejavu_fonts
    ];
  };
in
python3Packages.buildPythonApplication {
  pname = "glyphscape";
  version = "0.1.0";
  pyproject = true; # nixpkgs < 24.05: replace with `format = "pyproject";`

  src = ../.;

  build-system = [ python3Packages.setuptools ];

  propagatedBuildInputs = with python3Packages; [
    pillow
    requests
    fonttools
  ];

  makeWrapperArgs = [
    "--prefix PATH : ${lib.makeBinPath [ chafa fontconfig ]}"
    "--set FONTCONFIG_FILE ${fontsConf}"
  ];

  # No test suite yet; the pipeline is exercised via `glyphscape render`.
  doCheck = false;

  meta = {
    description = "Daily GNOME wallpaper: a photo rendered as a circular medallion of mixed-script glyphs on black";
    mainProgram = "glyphscape";
    platforms = lib.platforms.linux;
  };
}
