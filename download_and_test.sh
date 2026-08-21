#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
echo "download_and_test.sh is retained for compatibility; upstream files are imported into external/upstream/." >&2
exec "$SCRIPT_DIR/scripts/import_upstream_plugins.sh" "$@"
