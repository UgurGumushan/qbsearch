#!/bin/bash
set -euo pipefail

# Install every plugin, its icon sidecar, and plugin support JSON files into
# qBittorrent's macOS nova3 engines directory. Quit qBittorrent first so it
# reloads the files and icons on its next launch.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
PLUGINS_DIR="$REPO_ROOT/plugins"
ICONS_DIR="$REPO_ROOT/icons"
ENGINES_DIR="${QBITTORRENT_ENGINES_DIR:-$HOME/Library/Application Support/qBittorrent/nova3/engines}"

if pgrep -x qBittorrent >/dev/null 2>&1; then
    echo "Please quit qBittorrent before running this installer." >&2
    exit 1
fi

if [ ! -d "$PLUGINS_DIR" ]; then
    echo "Plugin directory not found: $PLUGINS_DIR" >&2
    exit 1
fi

mkdir -p "$ENGINES_DIR"

plugin_count=0
icon_count=0
support_count=0
missing_icons=0

for plugin in "$PLUGINS_DIR"/*.py; do
    [ -f "$plugin" ] || continue
    filename=${plugin##*/}
    stem=${filename%.py}
    cp -f "$plugin" "$ENGINES_DIR/$filename"
    plugin_count=$((plugin_count + 1))

    icon="$ICONS_DIR/$stem.ico"
    if [ -f "$icon" ]; then
        cp -f "$icon" "$ENGINES_DIR/$stem.ico"
        icon_count=$((icon_count + 1))
    else
        echo "warning: no icon asset for $stem" >&2
        missing_icons=$((missing_icons + 1))
    fi
done

# rutor.json is a plugin support file. Preserve an existing local copy because
# users may have configured proxy settings in it.
for support in "$PLUGINS_DIR"/*.json; do
    [ -f "$support" ] || continue
    filename=${support##*/}
    if [ ! -e "$ENGINES_DIR/$filename" ]; then
        cp -f "$support" "$ENGINES_DIR/$filename"
        support_count=$((support_count + 1))
    else
        echo "preserved existing support file: $filename"
    fi
done

echo "Installed $plugin_count plugins, $icon_count icons, and $support_count support files."
if [ "$missing_icons" -gt 0 ]; then
    echo "$missing_icons plugin(s) have no icon asset in $ICONS_DIR." >&2
fi
echo "Launch qBittorrent to load the installed plugins and icons."
