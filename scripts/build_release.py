#!/usr/bin/env python3
"""Build a self-contained release archive for qBittorrent users."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple, cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.plugin_catalog import ROOT, Catalog, catalog_entries, load_catalog, validate_catalog


class Arguments(NamedTuple):
    version: str
    output: Path


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(description="Build a qBittorrent plugin release ZIP.")
    _ = parser.add_argument(
        "--version",
        default="dev",
        help="release label used for the archive directory and filename (default: dev)",
    )
    _ = parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "working" / "qbsearch-dev.zip",
        help="output ZIP path (default: working/qbsearch-dev.zip)",
    )
    parsed = parser.parse_args()
    return Arguments(version=cast(str, parsed.version), output=cast(Path, parsed.output))


def archive_files(catalog: Catalog) -> list[Path]:
    entries = catalog_entries(catalog)
    files = [
        ROOT / "README.md",
        ROOT / "INSTALL.md",
        ROOT / "PLUGINS.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "CHANGELOG.md",
        ROOT / "ATTRIBUTIONS.md",
        ROOT / "LICENSE.md",
        ROOT / "catalog" / "plugins.json",
        ROOT / "scripts" / "install_plugins.py",
        ROOT / "scripts" / "plugin_catalog.py",
        ROOT / "install_plugins.sh",
        ROOT / "install_plugins.ps1",
    ]
    for entry in entries:
        plugin_id = str(entry["id"])
        files.append(ROOT / "plugins" / (plugin_id + ".py"))
        files.append(ROOT / str(entry["icon"]))
    return [path for path in files if path.is_file()]


def main() -> int:
    args = parse_args()
    if not args.version or any(char in args.version for char in '\\/:*?"<>|'):
        raise SystemExit("ERROR: --version contains invalid archive characters")
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    if errors:
        for error in errors:
            print("ERROR: " + error)
        return 1
    files = archive_files(catalog)
    prefix = "qbsearch-" + args.version
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "version": args.version,
        "plugin_count": len(catalog_entries(catalog)),
        "plugins": [str(entry["id"]) for entry in catalog_entries(catalog)],
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive_name = prefix + "/" + str(path.relative_to(ROOT))
            archive.write(path, archive_name)
        archive.writestr(
            prefix + "/release-manifest.json",
            json.dumps(manifest, indent=2) + "\n",
        )
    print("Built " + str(output) + " with " + str(len(catalog_entries(catalog))) + " plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
