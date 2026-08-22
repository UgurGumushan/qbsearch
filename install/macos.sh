#!/bin/sh
set -eu

# Install the complete qBittorrent nova3 engine collection from this checkout
# or release archive. This script intentionally has no command-line options.

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

home_dir=${HOME:-}
if [ -z "$home_dir" ]; then
    home_dir=$(CDPATH= cd ~ && pwd)
fi
DESTINATION="$home_dir/Library/Application Support/qBittorrent/nova3/engines"

if [ ! -d "$ROOT_DIR/plugins" ] || [ ! -d "$ROOT_DIR/icons" ]; then
    printf '%s\n' "ERROR: could not find the plugins and icons directories next to this installer." >&2
    exit 1
fi

plugin_count=0
icon_count=0
support_count=0

for source in "$ROOT_DIR"/plugins/*.py; do
    [ -f "$source" ] || continue
    plugin_count=$((plugin_count + 1))
    plugin_name=${source##*/}
    plugin_id=${plugin_name%.py}
    [ -f "$ROOT_DIR/icons/$plugin_id.ico" ] && icon_count=$((icon_count + 1))
done

for source in "$ROOT_DIR"/plugins/*.json; do
    [ -f "$source" ] || continue
    support_count=$((support_count + 1))
done

if [ "$plugin_count" -eq 0 ]; then
    printf '%s\n' "ERROR: no plugin files were found." >&2
    exit 1
fi

total=$((plugin_count + icon_count + support_count))
mkdir -p "$DESTINATION"

if [ -t 1 ] && [ -z "${CI:-}" ]; then
    interactive=1
else
    interactive=0
fi

progress() {
    current=$1
    label=$2
    if [ "$interactive" -eq 1 ]; then
        case $((current % 4)) in
            0) spinner='-' ;;
            1) spinner='\' ;;
            2) spinner='|' ;;
            *) spinner='/' ;;
        esac
        printf '\r%s Installing [%s/%s] %s' "$spinner" "$current" "$total" "$label"
    else
        printf '[%s/%s] %s\n' "$current" "$total" "$label"
    fi
}

printf 'Installing %s plugin(s) into %s\n' "$plugin_count" "$DESTINATION"
current=0

for source in "$ROOT_DIR"/plugins/*.py; do
    [ -f "$source" ] || continue
    file_name=${source##*/}
    cp "$source" "$DESTINATION/$file_name"
    current=$((current + 1))
    progress "$current" "$file_name"

    plugin_id=${file_name%.py}
    icon="$ROOT_DIR/icons/$plugin_id.ico"
    if [ -f "$icon" ]; then
        icon_name=${icon##*/}
        cp "$icon" "$DESTINATION/$icon_name"
        current=$((current + 1))
        progress "$current" "$icon_name"
    fi
done

for source in "$ROOT_DIR"/plugins/*.json; do
    [ -f "$source" ] || continue
    file_name=${source##*/}
    target="$DESTINATION/$file_name"
    if [ -e "$target" ]; then
        current=$((current + 1))
        progress "$current" "preserved $file_name"
    else
        cp "$source" "$target"
        current=$((current + 1))
        progress "$current" "$file_name"
    fi
done

if [ "$interactive" -eq 1 ]; then
    printf '\rInstalled %s file(s) into %s\n' "$total" "$DESTINATION"
else
    printf 'Installed %s file(s) into %s\n' "$total" "$DESTINATION"
fi
printf '%s\n' 'Done. Quit and relaunch qBittorrent if it was running.'
