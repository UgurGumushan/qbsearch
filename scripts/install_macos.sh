#!/bin/sh
set -eu

# Backward-compatible macOS entry point. The shared installer also supports
# Linux, Windows, --plugin, --destination, --dry-run, and --no-icons.
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/install_plugins.py" "$@"
