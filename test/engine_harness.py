"""Offline qBittorrent nova3 installability harness.

The public command remains ``python3 test/engines.py``.  This module keeps the
qBittorrent compatibility setup and per-plugin checks together while leaving
the command adapter intentionally small.
"""

from __future__ import annotations

import glob
import importlib.machinery
import importlib.util
import os
import re
import sys
import types
from typing import TypedDict, Union, cast

# The compatibility harness intentionally exercises importlib's dynamic loader
# API, whose Python 3.9 types are incomplete.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false

# qBitt's nova3 dir (holds helpers.py, novaprinter.py, socks.py, nova2.py).
QB_NOVA3 = os.path.expanduser("~/Library/Application Support/qBittorrent/nova3")
# qBitt's log, which records the Python interpreter it resolved to.
QB_LOG = os.path.expanduser("~/Library/Application Support/qBittorrent/logs/qbittorrent.log")


def detect_qbitt_python() -> tuple[int, int] | None:
    """Return the (major, minor) version qBitt uses, parsed from its log."""
    for path in (QB_LOG, QB_LOG + ".bak"):
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        # newest match wins; the log is chronological
        matches = cast(
            list[str],
            re.findall(r'Found Python executable.*?Version:\s*"(\d+\.\d+)', text),
        )
        if matches:
            major, minor = matches[-1].split(".")
            return (int(major), int(minor))
    return None


def ensure_qbitt_python() -> None:
    """Re-exec under the same Python qBitt uses, if the current one is newer."""
    target = detect_qbitt_python()
    if target is None:
        print(
            "NOTE: could not detect qBitt's Python from its log; "
            + f"testing under the current interpreter ({sys.version.split()[0]})."
        )
        return
    cur = (sys.version_info.major, sys.version_info.minor)
    if cur <= target:
        return  # current interpreter is old enough; PEP 604 etc. would fail here too
    # current interpreter is newer than qBitt's -- re-exec under an older one
    for candidate in (
        "/usr/bin/python3",
        (
            f"/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
            f"Python3.framework/Versions/{target[0]}.{target[1]}/bin/python3"
        ),
    ):
        if os.path.exists(candidate):
            print(
                f"NOTE: qBitt uses Python {target[0]}.{target[1]} but this is Python "
                + f"{cur[0]}.{cur[1]}; re-execing under {candidate} to match qBitt."
            )
            os.execv(candidate, [candidate] + sys.argv)
    print(
        f"NOTE: qBitt uses Python {target[0]}.{target[1]} but no matching interpreter was found; "
        + f"testing under the current interpreter ({sys.version.split()[0]})."
    )


def load_qbitt_modules() -> bool:
    """Make qBitt's real helpers/novaprinter/socks importable, if available."""
    if os.path.isdir(QB_NOVA3):
        sys.path.insert(0, QB_NOVA3)
        return True
    # Fallback: minimal stubs matching qBitt's real modules (3.9-compatible).
    novaprinter = types.ModuleType("novaprinter")

    def any_size_to_bytes(value: object) -> object:
        return value

    def ignore_result(*_args: object, **_kwargs: object) -> None:
        return None

    vars(novaprinter).update(
        {
            "SearchResults": TypedDict(
                "SearchResults",
                {
                    "link": str,
                    "name": str,
                    "size": Union[float, int, str],
                    "seeds": int,
                    "leech": int,
                    "engine_url": str,
                    "desc_link": str,
                    "pub_date": int,
                },
            ),
            "anySizeToBytes": any_size_to_bytes,
            "prettyPrinter": ignore_result,
        }
    )
    sys.modules["novaprinter"] = novaprinter

    helpers = types.ModuleType("helpers")

    def empty_text(*_args: object, **_kwargs: object) -> str:
        return ""

    def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    def identity(value: object) -> object:
        return value

    vars(helpers).update(
        {
            "retrieve_url": empty_text,
            "download_file": empty_text,
            "enable_socks_proxy": no_op,
            "htmlentitydecode": identity,
            "_headers": {},
        }
    )
    sys.modules["helpers"] = helpers

    socks = types.ModuleType("socks")
    vars(socks).update(
        {
            "PROXY_TYPE_SOCKS4": 1,
            "PROXY_TYPE_SOCKS5": 2,
            "socksocket": object,
            "setdefaultproxy": no_op,
            "set_default_proxy": no_op,
        }
    )
    sys.modules["socks"] = socks
    return False


def version_is_valid(version: str) -> bool:
    """qBitt's Version<2>::fromString: exactly 2 numeric components."""
    parts = version.strip().split(".")
    if len(parts) != 2:
        return False
    return all(part.isdigit() for part in parts)


def read_version(path: str) -> str | None:
    """Read the #VERSION: line the way qBitt does (spaces stripped)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.replace(" ", "")
            if stripped.upper().startswith("#VERSION:"):
                return stripped[len("#VERSION:") :].strip()
    return None


def check(path: str) -> str | None:
    """Replicate nova2.import_engine(): import module, getattr(module, stem)."""
    stem = os.path.basename(path)[:-3]
    _ = sys.modules.pop(stem, None)
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        return "cannot load module"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[stem] = mod
    if isinstance(spec.loader, importlib.machinery.SourceFileLoader):
        spec.loader.exec_module(mod)
    else:
        raise TypeError(f"unexpected loader type {type(spec.loader)!r}")
    cls = cast(object, getattr(mod, stem, None))
    if cls is None:
        return f"class/filename mismatch: no class named '{stem}'"
    missing = [attribute for attribute in ("name", "url") if not hasattr(cls, attribute)]
    if missing:
        return f"missing class attrs: {missing}"
    return None


def plugin_paths(plugin_dir: str) -> list[str]:
    """Return either the requested single plugin or all plugins in a directory."""
    if os.path.isfile(plugin_dir):
        return [plugin_dir]
    return sorted(glob.glob(os.path.join(plugin_dir, "*.py")))


def main(raw_args: list[str] | None = None) -> int:
    """Run installability and version checks for a plugin path or directory."""
    args = sys.argv[1:] if raw_args is None else raw_args
    plugin_dir = args[0] if args else "plugins"
    ensure_qbitt_python()
    using_real = load_qbitt_modules()

    ok: list[tuple[str, str | None]] = []
    broken: list[tuple[str, str | None]] = []
    bad_version: list[tuple[str, str | None]] = []
    for path in plugin_paths(plugin_dir):
        stem = os.path.basename(path)[:-3]
        version = read_version(path)
        if version is None or not version_is_valid(version):
            bad_version.append((stem, version))
        try:
            why = check(path)
        except Exception as error:
            detail = str(error).splitlines()[-1] if str(error) else error
            why = f"{type(error).__name__}: {detail}"
        finally:
            _ = sys.modules.pop(stem, None)
        (broken if why else ok).append((stem, why) if why else (stem, None))

    total = len(ok) + len(broken)
    print(
        f"Python {sys.version.split()[0]} | qBitt nova3 modules: "
        + f"{'real (from profile)' if using_real else 'stub (fallback)'}"
    )
    print(f"=== INSTALLABLE ({len(ok)}/{total}) ===")
    print(", ".join(stem for stem, _ in ok))
    print()
    if broken:
        print(f"=== NOT INSTALLABLE ({len(broken)}) ===")
        for stem, why in broken:
            print(f"      {stem:<18} {why}")
    else:
        print(f"All {total} plugins are installable.")
    print()
    if bad_version:
        print(f"=== INVALID #VERSION: ({len(bad_version)}, qBitt Version<2> = 2 numeric parts) ===")
        for stem, version in bad_version:
            print(f"      {stem:<18} {version!r}")
    else:
        print("All version strings are valid.")
    return 1 if broken or bad_version else 0


if __name__ == "__main__":
    sys.exit(main())
