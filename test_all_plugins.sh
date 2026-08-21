#!/bin/sh
# Run this file directly from a terminal; no coding agent is required.

set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$SCRIPT_DIR/scripts/test_all_plugins.py" "$@"
