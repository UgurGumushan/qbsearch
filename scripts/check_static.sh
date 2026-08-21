#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || {
    echo "error: run this command inside the repository" >&2
    exit 1
}

cd "$repo_root"

for tool in ruff basedpyright; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "error: $tool is not installed; run 'make dev-setup'" >&2
        exit 127
    fi
done

ruff check .
basedpyright
