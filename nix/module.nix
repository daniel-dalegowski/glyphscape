# home-manager module for Glyphscape.
#
# Usage, in a home-manager config:
#
#   imports = [ glyphscape.homeManagerModules.default ];
#   programs.glyphscape.enable = true;
#
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.programs.glyphscape;
  tomlFormat = pkgs.formats.toml { };

  backgroundsDir = "${config.home.homeDirectory}/.local/share/backgrounds/glyphscape";

  backgroundPropertiesXml = pkgs.writeText "glyphscape.xml" ''
    <?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE wallpapers SYSTEM "gnome-wp-list.dtd">
    <wallpapers>
      <wallpaper deleted="false">
        <name>Glyphscape</name>
        <filename>${backgroundsDir}/live.png</filename>
        ${lib.optionalString (cfg.settings.dark_variant or true)
          "<filename-dark>${backgroundsDir}/live-dark.png</filename-dark>"
        }
        <options>zoom</options>
        <shade_type>solid</shade_type>
        <pcolor>#000000</pcolor>
        <scolor>#000000</scolor>
      </wallpaper>
    </wallpapers>
  '';
in
{
  options.programs.glyphscape = {
    enable = lib.mkEnableOption "Glyphscape, a daily mixed-script-glyph GNOME wallpaper";

    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.callPackage ./package.nix { };
      description = "The glyphscape package to use.";
    };

    settings = lib.mkOption {
      type = tomlFormat.type;
      default = { };
      description = ''
        Settings written to ~/.config/glyphscape/config.toml. See the
        README's Configuration table for the full key reference.
      '';
      example = lib.literalExpression ''
        {
          sources = [ "wikimedia" "bing" "local" ];
          palette = "qud";       # or "none" to fall back to `color`
          glyph.script = "mixed"; # cjk/khmer/thai/myanmar/sinhala/braille/symbols/mixed
          circle.radius = 0.75;
          circle.feather = 0.0;
        }
      '';
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [ cfg.package ];

    xdg.configFile."glyphscape/config.toml".source = tomlFormat.generate "glyphscape-config.toml" cfg.settings;

    xdg.dataFile."gnome-background-properties/glyphscape.xml".source = backgroundPropertiesXml;

    systemd.user.services.glyphscape = {
      Unit.Description = "Fetch and render today's Glyphscape wallpaper";
      Service = {
        Type = "oneshot";
        ExecStart = "${cfg.package}/bin/glyphscape";
      };
    };

    systemd.user.timers.glyphscape = {
      Unit.Description = "Daily timer for Glyphscape";
      Timer = {
        OnCalendar = "daily";
        Persistent = true;
        OnStartupSec = "2min";
      };
      Install.WantedBy = [ "timers.target" ];
    };
  };
}
