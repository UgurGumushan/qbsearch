#!/usr/bin/env python3
"""Validate or generate the repository's plugin catalog and index."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NamedTuple, cast

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.plugin_catalog import (
    CATALOG_PATH,
    DOCS_PATH,
    bootstrap_catalog,
    catalog_entries,
    load_catalog,
    refresh_catalog,
    render_plugin_docs,
    validate_catalog,
    write_catalog,
)


class Arguments(NamedTuple):
    bootstrap: bool
    write: bool
    docs: bool
    refresh: bool
    check: bool


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(
        description="Validate or generate catalog/plugins.json and PLUGINS.md."
    )
    _ = parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="create a catalog from the existing plugins and live-query profile",
    )
    _ = parser.add_argument(
        "--write",
        action="store_true",
        help="write the catalog when used with --bootstrap",
    )
    _ = parser.add_argument(
        "--docs",
        action="store_true",
        help="write the generated PLUGINS.md index",
    )
    _ = parser.add_argument(
        "--refresh",
        action="store_true",
        help="fill catalog license fields from LICENSE.md without overwriting edits",
    )
    _ = parser.add_argument(
        "--check",
        action="store_true",
        help="validate the catalog and generated index without changing files",
    )
    parsed = parser.parse_args()
    return Arguments(
        bootstrap=cast(bool, parsed.bootstrap),
        write=cast(bool, parsed.write),
        docs=cast(bool, parsed.docs),
        refresh=cast(bool, parsed.refresh),
        check=cast(bool, parsed.check),
    )


def main() -> int:
    args = parse_args()
    if args.bootstrap and args.refresh:
        print("ERROR: choose only one of --bootstrap and --refresh", file=sys.stderr)
        return 2
    if args.bootstrap:
        if CATALOG_PATH.exists():
            print(
                "ERROR: catalog already exists; edit it directly instead of bootstrapping again.",
                file=sys.stderr,
            )
            return 1
        catalog = bootstrap_catalog()
        errors = validate_catalog(catalog)
        if errors:
            for error in errors:
                print("ERROR: " + error, file=sys.stderr)
            return 1
        if args.write:
            write_catalog(catalog)
            print("Wrote " + str(CATALOG_PATH.relative_to(CATALOG_PATH.parents[1])))
    else:
        try:
            catalog = load_catalog()
        except (TypeError, ValueError) as error:
            print("ERROR: " + str(error), file=sys.stderr)
            return 1
        if args.refresh:
            catalog = refresh_catalog(catalog)
            write_catalog(catalog)
            print("Refreshed " + str(CATALOG_PATH.relative_to(CATALOG_PATH.parents[1])))

    errors = validate_catalog(catalog)
    if errors:
        for error in errors:
            print("ERROR: " + error, file=sys.stderr)
        return 1

    if args.docs:
        _ = DOCS_PATH.write_text(render_plugin_docs(catalog), encoding="utf-8")
        print("Wrote " + str(DOCS_PATH.relative_to(DOCS_PATH.parents[0])))
    elif args.check:
        expected = render_plugin_docs(catalog)
        if not DOCS_PATH.is_file() or DOCS_PATH.read_text(encoding="utf-8") != expected:
            print("ERROR: PLUGINS.md is out of date; run with --docs", file=sys.stderr)
            return 1

    print("Catalog valid: " + str(len(catalog_entries(catalog))) + " plugins.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
