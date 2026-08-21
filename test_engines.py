#!/usr/bin/env python3
# Test whether every plugin in plugins/ is installable by qBittorrent (v5.2.3+).
#
# qBittorrent's nova2.py loads each engine with:
#     importlib.import_module("engines.<stem>")  then  getattr(module, <stem>)
# and searchpluginmanager.cpp reads the class's .name / .url plus the #VERSION: line.
#
# This harness is faithful to qBitt in three ways:
#    1. It loads qBitt's REAL nova3 modules (helpers, novaprinter, socks, nova2)
#       from the user's qBitt profile, instead of hand-written stubs.
#    2. It runs under the SAME Python qBitt uses. qBitt logs the interpreter it
#       found ("Found Python executable ... Version: X.Y.Z"); we parse that and
#       re-exec under the matching python3 if the current one is newer, so we catch
#       version-specific breakage (e.g. PEP 604 "str | None" needs Python >= 3.10).
#    3. It validates each #VERSION: against qBitt's Version<2> parser (2 numeric
#       components) to catch version-string bugs that don't block install.
#
# Usage:  python3 test_engines.py              (tests plugins/)
#          python3 test_engines.py <dir>       (tests another directory)
#          python3 test_engines.py <plugin.py>  (tests one plugin)

import glob
import importlib.machinery
import importlib.util
import os
import re
import sys

PLUGIN_DIR = sys.argv[1] if len(sys.argv) > 1 else "plugins"

# qBitt's nova3 dir (holds helpers.py, novaprinter.py, socks.py, nova2.py).
QB_NOVA3 = os.path.expanduser("~/Library/Application Support/qBittorrent/nova3")
# qBitt's log, which records the Python interpreter it resolved to.
QB_LOG = os.path.expanduser("~/Library/Application Support/qBittorrent/logs/qbittorrent.log")


def detect_qbitt_python():
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
        matches = re.findall(r'Found Python executable.*?Version:\s*"(\d+\.\d+)', text)
        if matches:
            major, minor = matches[-1].split(".")
            return (int(major), int(minor))
    return None


def ensure_qbitt_python():
    """Re-exec under the same Python qBitt uses, if the current one is newer."""
    target = detect_qbitt_python()
    if target is None:
        print(f"NOTE: could not detect qBitt's Python from its log; "
              f"testing under the current interpreter ({sys.version.split()[0]}).")
        return
    cur = (sys.version_info.major, sys.version_info.minor)
    if cur <= target:
        return  # current interpreter is old enough; PEP 604 etc. would fail here too
    # current interpreter is newer than qBitt's -- re-exec under an older one
    for candidate in ("/usr/bin/python3",
                      (f"/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
                       f"Python3.framework/Versions/{target[0]}.{target[1]}/bin/python3")):
        if os.path.exists(candidate):
            print(f"NOTE: qBitt uses Python {target[0]}.{target[1]} but this is Python "
                  f"{cur[0]}.{cur[1]}; re-execing under {candidate} to match qBitt.")
            os.execv(candidate, [candidate] + sys.argv)
    print(f"NOTE: qBitt uses Python {target[0]}.{target[1]} but no matching interpreter was found; "
          f"testing under the current interpreter ({sys.version.split()[0]}).")


def load_qbitt_modules():
    """Make qBitt's real helpers/novaprinter/socks importable, if available."""
    if os.path.isdir(QB_NOVA3):
        sys.path.insert(0, QB_NOVA3)
        return True
    # Fallback: minimal stubs matching qBitt's real modules (3.9-compatible).
    import types
    from typing import TypedDict, Union

    novaprinter = types.ModuleType("novaprinter")
    vars(novaprinter).update({
        "SearchResults": TypedDict("SearchResults", {
            "link": str, "name": str, "size": Union[float, int, str],
            "seeds": int, "leech": int, "engine_url": str,
            "desc_link": str, "pub_date": int,
        }),
        "anySizeToBytes": lambda s: s,
        "prettyPrinter": lambda *a, **k: None,
    })
    sys.modules["novaprinter"] = novaprinter

    helpers = types.ModuleType("helpers")
    vars(helpers).update({
        "retrieve_url": lambda *a, **k: "",
        "download_file": lambda *a, **k: "",
        "enable_socks_proxy": lambda *a, **k: None,
        "htmlentitydecode": lambda s: s,
        "_headers": {},
    })
    sys.modules["helpers"] = helpers

    socks = types.ModuleType("socks")
    vars(socks).update({
        "PROXY_TYPE_SOCKS4": 1,
        "PROXY_TYPE_SOCKS5": 2,
        "socksocket": object,
        "setdefaultproxy": lambda *a, **k: None,
        "set_default_proxy": lambda *a, **k: None,
    })
    sys.modules["socks"] = socks
    return False


def version_is_valid(v):
    """qBitt's Version<2>::fromString: exactly 2 numeric components."""
    parts = v.strip().split(".")
    if len(parts) != 2:
        return False
    return all(p.isdigit() for p in parts)


def read_version(path):
    """Read the #VERSION: line the way qBitt does (spaces stripped)."""
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            stripped = line.replace(" ", "")
            if stripped.upper().startswith("#VERSION:"):
                return stripped[len("#VERSION:"):].strip()
    return None


def check(path):
    """Replicate nova2.import_engine(): import module, getattr(module, stem)."""
    stem = os.path.basename(path)[:-3]
    sys.modules.pop(stem, None)
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        return "cannot load module"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[stem] = mod
    if isinstance(spec.loader, importlib.machinery.SourceFileLoader):
        spec.loader.exec_module(mod)
    else:
        raise TypeError(f"unexpected loader type {type(spec.loader)!r}")
    cls = getattr(mod, stem, None)
    if cls is None:
        return f"class/filename mismatch: no class named '{stem}'"
    missing = [a for a in ("name", "url") if not hasattr(cls, a)]
    if missing:
        return f"missing class attrs: {missing}"
    return None


def plugin_paths():
    """Return either the requested single plugin or all plugins in a directory."""
    if os.path.isfile(PLUGIN_DIR):
        return [PLUGIN_DIR]
    return sorted(glob.glob(os.path.join(PLUGIN_DIR, "*.py")))


def main():
    ensure_qbitt_python()
    using_real = load_qbitt_modules()

    ok, broken, bad_version = [], [], []
    for path in plugin_paths():
        stem = os.path.basename(path)[:-3]
        v = read_version(path)
        if v is None or not version_is_valid(v):
            bad_version.append((stem, v))
        try:
            why = check(path)
        except Exception as e:
            why = f"{type(e).__name__}: {str(e).splitlines()[-1] if str(e) else e}"
        finally:
            sys.modules.pop(stem, None)
        (broken if why else ok).append((stem, why) if why else (stem, None))

    total = len(ok) + len(broken)
    print(f"Python {sys.version.split()[0]} | qBitt nova3 modules: "
          f"{'real (from profile)' if using_real else 'stub (fallback)'}")
    print(f"=== INSTALLABLE ({len(ok)}/{total}) ===")
    print(", ".join(s for s, _ in ok))
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
        for stem, v in bad_version:
            print(f"      {stem:<18} {v!r}")
    else:
        print("All version strings are valid.")
    return 1 if broken or bad_version else 0


if __name__ == "__main__":
    sys.exit(main())
