#!/usr/bin/env python3
"""Load, validate, and generate metadata for the standalone engines.

The catalog is development metadata only.  qBittorrent still installs and
executes each file in ``plugins/`` independently; no catalog module is needed
at runtime.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugins"
ICON_DIR = ROOT / "icons"
CATALOG_PATH = ROOT / "catalog" / "plugins.json"
DOCS_PATH = ROOT / "PLUGINS.md"
RAW_PLUGIN_BASE = "https://raw.githubusercontent.com/UgurGumushan/qbsearch/main/plugins/"

VALID_CATEGORIES = {
    "adult",
    "anime",
    "books",
    "games",
    "general",
    "movies",
    "music",
    "software",
    "tv",
}
VALID_STATUSES = {"active", "intermittent", "unavailable", "requires-account", "retired"}


class CatalogEntry(TypedDict):
    id: str
    name: str
    site_url: str
    category: str
    default_query: str
    status: str
    icon: str
    requires_auth: bool
    source_url: str | None
    license: str | None
    notes: str


class Catalog(TypedDict, total=False):
    schema_version: int
    plugins: list[CatalogEntry]


# Used only when bootstrapping a new catalog entry.  The generated JSON is the
# source of truth and can be edited when a site changes its classification.
CATEGORY_HINTS = {
    "adult": {"mypornclub", "nyaa_phuong", "nyaapantsu", "sukebeisi", "xxxclubto"},
    "anime": {
        "acgrip",
        "anidex",
        "animetosho",
        "dmhy",
        "mikan",
        "mikanani",
        "nekobt",
        "nyaasi",
        "subsplease",
        "tokyotoshokan",
    },
    "books": {"audiobookbay", "darklibria"},
    "games": {"ali213", "dodi_repacks", "fitgirl_repacks", "goggames", "onlinefix", "smallgames"},
    "movies": {
        "apachetorrent",
        "calidadtorrent",
        "cpasbien",
        "divxtotal",
        "dontorrent",
        "elitetorrent",
        "esmeraldatorrent",
        "maxitorrent",
        "mejortorrent",
        "naranjatorrent",
        "pirateiro",
        "redetorrent",
        "therarbg",
        "tomadivx",
        "torrent9",
        "traht",
        "yts",
    },
    "software": {"academictorrents", "bt4gprx", "rockbox"},
    "tv": {"eztvx"},
}


def _string_value(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _assignment_value(node: ast.AST, name: str) -> ast.AST | None:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == name for target in node.targets
    ):
        return node.value
    if (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == name
    ):
        return node.value
    return None


def inspect_plugin(path: Path) -> dict[str, str]:
    """Read the installable class's name and URL without importing the plugin."""
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=str(path))
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            if node.value is None:
                continue
            targets: Iterable[ast.AST]
            if isinstance(node, ast.Assign):
                targets = node.targets
            else:
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    value = _string_value(node.value, constants)
                    if value is not None:
                        constants[target.id] = value

    stem = path.stem
    classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
    class_name = stem if stem in classes else None
    if class_name is None:
        for node in tree.body:
            value = _assignment_value(node, stem)
            if isinstance(value, ast.Name) and value.id in classes:
                class_name = value.id
                break
    if class_name is None:
        raise ValueError("could not find the qBittorrent engine class")

    engine = classes[class_name]
    attributes: dict[str, str] = {}
    for node in engine.body:
        for attribute in ("name", "url"):
            value_node = _assignment_value(node, attribute)
            if value_node is not None:
                value = _string_value(value_node, constants)
                if value is not None:
                    attributes[attribute] = value
    missing = [attribute for attribute in ("name", "url") if attribute not in attributes]
    if missing:
        raise ValueError("missing class attribute(s): " + ", ".join(missing))
    return {"name": attributes["name"], "site_url": attributes["url"]}


def discover_plugins() -> list[Path]:
    return sorted(path for path in PLUGIN_DIR.glob("*.py") if path.is_file())


def _category_for(stem: str) -> str:
    for category, stems in CATEGORY_HINTS.items():
        if stem in stems:
            return category
    return "general"


def _legacy_queries() -> dict[str, str]:
    """Read the old runner's profile once while bootstrapping the catalog."""
    runner = ROOT / "scripts" / "test_all_plugins.py"
    if not runner.exists():
        return {}
    tree = ast.parse(runner.read_text(encoding="utf-8", errors="replace"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "DEFAULT_LIVE_QUERIES"
            for target in node.targets
        ):
            continue
        value = cast(dict[object, object], cast(object, ast.literal_eval(node.value)))
        return {str(key): str(query) for key, query in value.items()}
    return {}


def _license_map() -> dict[str, str]:
    license_file = ROOT / "LICENSE.md"
    if not license_file.is_file():
        return {}
    pattern: re.Pattern[str] = re.compile(
        r"^\| \[([A-Za-z0-9_]+)\.py\]\(plugins/[^)]+\) \| ([^|]+) \|$", re.MULTILINE
    )
    matches = cast(
        list[tuple[str, str]],
        pattern.findall(license_file.read_text(encoding="utf-8")),
    )
    return {stem: license_name.strip() for stem, license_name in matches}


def bootstrap_catalog() -> Catalog:
    queries = _legacy_queries()
    licenses = _license_map()
    entries: list[CatalogEntry] = []
    for path in discover_plugins():
        metadata = inspect_plugin(path)
        entry: CatalogEntry = {
            "id": path.stem,
            "name": metadata["name"],
            "site_url": metadata["site_url"],
            "category": _category_for(path.stem),
            "default_query": queries.get(path.stem, "ubuntu"),
            "status": "active",
            "icon": "icons/" + path.stem + ".ico",
            "requires_auth": False,
            "source_url": None,
            "license": licenses.get(path.stem),
            "notes": "",
        }
        entries.append(entry)
    return {"schema_version": 1, "plugins": entries}


def refresh_catalog(catalog: Catalog) -> Catalog:
    """Fill metadata that is already documented elsewhere without overwriting edits."""
    licenses = _license_map()
    for entry in catalog_entries(catalog):
        plugin_id = str(entry["id"])
        if entry.get("license") is None:
            entry["license"] = licenses.get(plugin_id)
    return catalog


def load_catalog(path: Path = CATALOG_PATH) -> Catalog:
    try:
        value: object = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError as error:
        raise ValueError("catalog is missing: " + str(path)) from error
    except json.JSONDecodeError as error:
        raise ValueError("catalog is not valid JSON: " + str(error)) from error
    if not isinstance(value, dict):
        raise TypeError("catalog root must be an object")
    return cast(Catalog, cast(object, value))


def write_catalog(catalog: Catalog, path: Path = CATALOG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def catalog_entries(catalog: Catalog) -> list[CatalogEntry]:
    entries = catalog.get("plugins")
    if not isinstance(entries, list):
        raise TypeError("catalog.plugins must be an array")
    raw_entries = cast(list[object], cast(object, entries))
    typed_entries: list[CatalogEntry] = []
    for entry in raw_entries:
        if not isinstance(entry, dict):
            raise TypeError("every catalog.plugins entry must be an object")
        typed_entries.append(cast(CatalogEntry, cast(object, entry)))
    return typed_entries


def validate_catalog(catalog: Catalog) -> list[str]:
    errors: list[str] = []
    if catalog.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    try:
        entries = catalog_entries(catalog)
    except (TypeError, ValueError) as error:
        return [str(error)]

    seen: set[str] = set()
    paths = {path.stem: path for path in discover_plugins()}
    for entry in entries:
        raw_entry = cast(dict[str, object], cast(object, entry))
        stem = raw_entry.get("id")
        if not isinstance(stem, str) or not stem:
            errors.append("plugin entry has an invalid id")
            continue
        if stem in seen:
            errors.append("duplicate catalog id: " + stem)
        seen.add(stem)
        required = ("name", "site_url", "category", "default_query", "status", "icon")
        missing = [field for field in required if field not in raw_entry]
        if missing:
            errors.append(stem + " is missing: " + ", ".join(missing))
            continue
        if stem not in paths:
            errors.append(stem + " is in the catalog but not in plugins/")
            continue
        if raw_entry["category"] not in VALID_CATEGORIES:
            errors.append(stem + " has invalid category: " + repr(raw_entry["category"]))
        if raw_entry["status"] not in VALID_STATUSES:
            errors.append(stem + " has invalid status: " + repr(raw_entry["status"]))
        if (
            not isinstance(raw_entry["default_query"], str)
            or not raw_entry["default_query"].strip()
        ):
            errors.append(stem + " must have a non-empty default_query")
        if raw_entry["icon"] != "icons/" + stem + ".ico":
            errors.append(stem + " icon must be icons/" + stem + ".ico")
        if not isinstance(raw_entry.get("requires_auth", False), bool):
            errors.append(stem + " requires_auth must be boolean")
        icon = ROOT / str(raw_entry["icon"])
        if not icon.is_file():
            errors.append(stem + " is missing icon: " + str(icon.relative_to(ROOT)))
        try:
            source_metadata = inspect_plugin(paths[stem])
        except (OSError, SyntaxError, ValueError) as error:
            errors.append(stem + " metadata cannot be inspected: " + str(error))
        else:
            if raw_entry["name"] != source_metadata["name"]:
                errors.append(stem + " catalog name does not match plugin class")
            if raw_entry["site_url"] != source_metadata["site_url"]:
                errors.append(stem + " catalog site_url does not match plugin class")

    missing = sorted(set(paths) - seen)
    if missing:
        errors.append("plugins missing from catalog: " + ", ".join(missing))
    return errors


def render_plugin_docs(catalog: Catalog) -> str:
    entries = catalog_entries(catalog)
    category_counts = Counter(str(entry["category"]) for entry in entries)
    status_counts = Counter(str(entry["status"]) for entry in entries)
    categories = ", ".join(
        category + " (" + str(category_counts[category]) + ")"
        for category in sorted(category_counts)
    )
    statuses = ", ".join(
        status + " (" + str(status_counts[status]) + ")" for status in sorted(status_counts)
    )
    lines = [
        "# Plugin catalog",
        "",
        "This file is generated from [`catalog/plugins.json`](catalog/plugins.json).",
        "Edit the JSON catalog and run `python3 scripts/generate_plugin_catalog.py --docs`.",
        "",
        "The `status` field describes repository support, not a guarantee that a remote",
        "site is online at this moment. Live tests contact the sites listed below.",
        "",
        "- Categories: " + categories,
        "- Status: " + statuses,
        "",
        "| Plugin | Category | Status | License | Site | Default live query | Install |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(
        entries, key=lambda item: (str(item["category"]), str(item["name"]).lower())
    ):
        name = str(entry["name"]).replace("|", "\\|")
        site_url = str(entry["site_url"])
        site = "[site](" + site_url + ")" if site_url else "—"
        query = str(entry["default_query"]).replace("|", "\\|")
        license_name = str(entry.get("license") or "—").replace("|", "\\|")
        if entry.get("notes"):
            query += " (" + str(entry["notes"]).replace("|", "\\|") + ")"
        lines.append(
            "| ["
            + name
            + "](plugins/"
            + str(entry["id"])
            + ".py) | "
            + str(entry["category"])
            + " | "
            + str(entry["status"])
            + " | "
            + license_name
            + " | "
            + site
            + " | `"
            + query
            + "` | [download]("
            + RAW_PLUGIN_BASE
            + str(entry["id"])
            + ".py) |"
        )
    lines.extend(
        [
            "",
            "`default live query` is only a safe smoke-test value. It is not a",
            "recommendation for content or a promise that the site returns results.",
            "",
        ]
    )
    return "\n".join(lines)
