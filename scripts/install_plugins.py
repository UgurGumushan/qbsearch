#!/usr/bin/env python3
"""Install standalone qBittorrent engines and their optional icons."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import NamedTuple, Optional, cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.plugin_catalog import (
    ROOT,
    CatalogEntry,
    catalog_entries,
    load_catalog,
    validate_catalog,
)

PLUGIN_DIR = ROOT / "plugins"


class Arguments(NamedTuple):
    plugin_ids: list[str] | None
    destination: Path | None
    no_icons: bool
    dry_run: bool


def default_destination() -> Path:
    override = os.environ.get("QBITTORRENT_ENGINES_DIR")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "qBittorrent" / "nova3" / "engines"
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if local_app_data:
            return Path(local_app_data) / "qBittorrent" / "nova3" / "engines"
        return Path.home() / "AppData" / "Local" / "qBittorrent" / "nova3" / "engines"
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "qBittorrent" / "nova3" / "engines"


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Install qBittorrent search plugins from this repository."
    )
    _ = parser.add_argument(
        "--plugin",
        action="append",
        dest="plugin_ids",
        help="install only this plugin id; may be repeated (default: all)",
    )
    _ = parser.add_argument(
        "--destination",
        type=Path,
        help="qBittorrent nova3/engines directory (default: platform-specific path)",
    )
    _ = parser.add_argument(
        "--no-icons",
        action="store_true",
        help="install .py engines without copying matching icon files",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would be installed without changing files",
    )
    parsed = parser.parse_args()
    return Arguments(
        plugin_ids=cast(Optional[list[str]], parsed.plugin_ids),
        destination=cast(Optional[Path], parsed.destination),
        no_icons=cast(bool, parsed.no_icons),
        dry_run=cast(bool, parsed.dry_run),
    )


def copy_file(source: Path, destination: Path, dry_run: bool) -> None:
    print("  " + str(source.relative_to(ROOT)) + " -> " + str(destination))
    if not dry_run:
        destination.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source, destination)


def select_entries(plugin_ids: list[str] | None) -> list[CatalogEntry]:
    catalog = load_catalog()
    errors = validate_catalog(catalog)
    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        raise ValueError("catalog validation failed")
    entries = {str(entry["id"]): entry for entry in catalog_entries(catalog)}
    if not plugin_ids:
        return [entries[plugin_id] for plugin_id in sorted(entries)]
    normalized = [plugin_id.removesuffix(".py") for plugin_id in plugin_ids]
    unknown = sorted(set(normalized) - set(entries))
    if unknown:
        raise ValueError("unknown plugin id(s): " + ", ".join(unknown))
    return [entries[plugin_id] for plugin_id in normalized]


def install(
    entries: Iterable[CatalogEntry], destination: Path, no_icons: bool, dry_run: bool
) -> int:
    entries = list(entries)
    print(
        ("Would install " if dry_run else "Installing ")
        + str(len(entries))
        + " plugin(s) into "
        + str(destination)
    )
    for entry in entries:
        plugin_id = str(entry["id"])
        copy_file(PLUGIN_DIR / (plugin_id + ".py"), destination / (plugin_id + ".py"), dry_run)
        if not no_icons:
            icon = ROOT / str(entry["icon"])
            if icon.is_file():
                copy_file(icon, destination / icon.name, dry_run)
            else:
                print("  warning: icon missing for " + plugin_id, file=sys.stderr)

    # Support files such as rutor.json may contain user settings. Preserve an
    # existing destination copy rather than overwriting it, and only install a
    # support file when its engine is part of this selection.
    selected_ids = {str(entry["id"]) for entry in entries}
    for source in sorted(PLUGIN_DIR.glob("*.json")):
        if source.stem not in selected_ids:
            continue
        target = destination / source.name
        if target.exists():
            print("  preserved existing " + str(target))
        else:
            copy_file(source, target, dry_run)
    print("Done. Quit and relaunch qBittorrent if it was running.")
    return 0


def main() -> int:
    args = parse_args()
    destination = (args.destination or default_destination()).expanduser().resolve()
    try:
        entries = select_entries(args.plugin_ids)
        return install(entries, destination, args.no_icons, args.dry_run)
    except (OSError, TypeError, ValueError) as error:
        print("ERROR: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
