#!/usr/bin/env python3
# Test whether every plugin in working/ is installable by qBittorrent (v5.2.3+).
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
# Usage:  python3 test_engines.py              (tests working/)
#          python3 test_engines.py <dir>       (tests another dir)

import glob
import importlib.util
import os
import re
import sys

WORKING = sys.argv[1] if len(sys.argv) > 1 else "working"

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
            text = open(path, encoding="utf-8", errors="replace").read()
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
        print("NOTE: could not detect qBitt's Python from its log; "
              "testing under the current interpreter (%s)." % sys.version.split()[0])
        return
    cur = (sys.version_info.major, sys.version_info.minor)
    if cur <= target:
        return  # current interpreter is old enough; PEP 604 etc. would fail here too
    # current interpreter is newer than qBitt's -- re-exec under an older one
    for candidate in ("/usr/bin/python3",
                      "/Applications/Xcode.app/Contents/Developer/Library/Frameworks/"
                      "Python3.framework/Versions/%d.%d/bin/python3" % target):
        if os.path.exists(candidate):
            print("NOTE: qBitt uses Python %d.%d but this is Python %d.%d; "
                  "re-execing under %s to match qBitt."
                  % (target[0], target[1], cur[0], cur[1], candidate))
            os.execv(candidate, [candidate] + sys.argv)
    print("NOTE: qBitt uses Python %d.%d but no matching interpreter was found; "
          "testing under the current interpreter (%s)."
          % (target[0], target[1], sys.version.split()[0]))


def load_qbitt_modules():
    """Make qBitt's real helpers/novaprinter/socks importable, if available."""
    if os.path.isdir(QB_NOVA3):
        sys.path.insert(0, QB_NOVA3)
        return True
    # Fallback: minimal stubs matching qBitt's real modules (3.9-compatible).
    import types
    from typing import TypedDict, Union

    novaprinter = types.ModuleType("novaprinter")
    novaprinter.SearchResults = TypedDict("SearchResults", {
        "link": str, "name": str, "size": Union[float, int, str],
        "seeds": int, "leech": int, "engine_url": str,
        "desc_link": str, "pub_date": int,
    })
    novaprinter.anySizeToBytes = lambda s: s
    novaprinter.prettyPrinter = lambda *a, **k: None
    sys.modules["novaprinter"] = novaprinter

    helpers = types.ModuleType("helpers")
    helpers.retrieve_url = lambda *a, **k: ""
    helpers.download_file = lambda *a, **k: ""
    helpers.enable_socks_proxy = lambda *a, **k: None
    helpers.htmlentitydecode = lambda s: s
    helpers._headers = {}
    sys.modules["helpers"] = helpers

    socks = types.ModuleType("socks")
    socks.PROXY_TYPE_SOCKS4 = 1
    socks.PROXY_TYPE_SOCKS5 = 2
    socks.socksocket = object
    socks.setdefaultproxy = lambda *a, **k: None
    socks.set_default_proxy = lambda *a, **k: None
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
    for line in open(path, encoding="utf-8", errors="replace"):
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
    spec.loader.exec_module(mod)
    cls = getattr(mod, stem, None)
    if cls is None:
        return "class/filename mismatch: no class named '%s'" % stem
    missing = [a for a in ("name", "url") if not hasattr(cls, a)]
    if missing:
        return "missing class attrs: %s" % missing
    return None


def main():
    ensure_qbitt_python()
    using_real = load_qbitt_modules()

    ok, broken, bad_version = [], [], []
    for path in sorted(glob.glob(os.path.join(WORKING, "*.py"))):
        stem = os.path.basename(path)[:-3]
        v = read_version(path)
        if v is None or not version_is_valid(v):
            bad_version.append((stem, v))
        try:
            why = check(path)
        except Exception as e:
            why = "%s: %s" % (type(e).__name__, str(e).splitlines()[-1] if str(e) else e)
        finally:
            sys.modules.pop(stem, None)
        (broken if why else ok).append((stem, why) if why else (stem, None))

    total = len(ok) + len(broken)
    print("Python %s | qBitt nova3 modules: %s"
          % (sys.version.split()[0], "real (from profile)" if using_real else "stub (fallback)"))
    print("=== INSTALLABLE (%d/%d) ===" % (len(ok), total))
    print(", ".join(s for s, _ in ok))
    print()
    if broken:
        print("=== NOT INSTALLABLE (%d) ===" % len(broken))
        for stem, why in broken:
            print("      %-18s %s" % (stem, why))
    else:
        print("All %d plugins are installable." % total)
    print()
    if bad_version:
        print("=== INVALID #VERSION: (%d, qBitt Version<2> = 2 numeric parts) ===" % len(bad_version))
        for stem, v in bad_version:
            print("      %-18s %r" % (stem, v))
    else:
        print("All version strings are valid.")
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
