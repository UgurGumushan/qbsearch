#!/usr/bin/env python3
"""Generate icons/<stem>.ico favicons for the qBittorrent search plugins.

For every plugins/<stem>.py plugin this script:
  1. extracts the base URL from the plugin class `url` attribute,
  2. fetches the site favicon (https://<host>/favicon.ico, falling back to
     Google's favicon service),
  3. converts it to a square ICO (downscaled to 32x32 if larger than 32)
     and writes it to icons/<stem>.ico,
  4. records the result in /tmp/icon_manifest.json.

Requires Pillow (PIL) for the image conversion. If Pillow is missing, the
script still extracts the URL map and writes the manifest, with every entry
marked ok=false.

Usage: python3 scripts/make_icons.py
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class _PillowImage(Protocol):
    size: tuple[int, int]

    def convert(self, mode: str) -> _PillowImage: ...

    def paste(self, image: _PillowImage, box: tuple[int, int]) -> None: ...

    def resize(self, size: tuple[int, int], resample: object) -> _PillowImage: ...

    def save(self, output: object, format: str | None = None, **kwargs: Any) -> None: ...


class _PillowResampling(Protocol):
    LANCZOS: object


class _PillowModule(Protocol):
    Resampling: _PillowResampling

    def open(self, data: object) -> _PillowImage: ...

    def new(
        self,
        mode: str,
        size: tuple[int, int],
        color: tuple[int, int, int, int],
    ) -> _PillowImage: ...


try:
    from PIL import Image as _loaded_pillow
except ImportError:
    _loaded_pillow = None

_pillow_module: _PillowModule | None = cast(_PillowModule | None, _loaded_pillow)

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS = REPO_ROOT / "plugins"
ICONS = REPO_ROOT / "icons"
MANIFEST = Path("/tmp/icon_manifest.json")

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
TIMEOUT = 10
MAX_SIZE = 32

RE_URL_ATTR = re.compile(
    r"""^[ \t]+url[ \t]*=[ \t]*['"](?P<u>https?://[^'"]+)['"]""",
    re.MULTILINE,
)
RE_URL_NAME = re.compile(
    r"^[ \t]+url[ \t]*=[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*$",
    re.MULTILINE,
)
RE_CONST = re.compile(
    r"^[ \t]*(?P<n>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*['\"](?P<v>https?://[^'\"]+)['\"]",
    re.MULTILINE,
)

# Hand-picked author-repo images from the qBitt search-plugins wiki, used
# when the normal favicon sources fail.
EXTRA = {
    "darklibria": "https://raw.githubusercontent.com/bugsbringer/qbit-plugins/master/darklibria.png",
    "magnetdl": "https://raw.githubusercontent.com/hannsen/qbittorrent_search_plugins/00e876a51f2cb45ee22071c56fc7ba52dc117721/magnetdl.png",
    "nyaapantsu": "https://raw.githubusercontent.com/4chenz/pantsu-plugin/master/pantsu.png",
    "rockbox": "https://raw.githubusercontent.com/Pireo/hello-world/master/rockbox.png",
    "torrent9": "https://raw.githubusercontent.com/menegop/qbfrench/master/torrent9.png",
    "uniondht": "https://raw.githubusercontent.com/msagca/qbittorrent-plugins/main/uniondht_icon.png",
}


def extract_url(path: Path) -> str | None:
    """Return the plugin's base URL, or None if it cannot be determined."""
    src = path.read_text(encoding="utf-8", errors="replace")
    m = RE_URL_ATTR.search(src)
    if m:
        return m.group("u")
    # Fallback: `url = SOME_CONST` referencing a module-level constant.
    m = RE_URL_NAME.search(src)
    if m:
        c = RE_CONST.search(src)
        while c:
            if c.group("n") == m.group(1):
                return c.group("v")
            c = RE_CONST.search(src, c.end())
    return None


def fetch(url: str) -> tuple[bytes | None, str | None]:
    """GET `url` with a normal browser User-Agent. Returns (data, error)."""
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=TIMEOUT) as resp:
            data = resp.read()
        if data:
            return data, None
        return None, "empty response"
    except Exception as exc:  # URLError, HTTPError, ssl errors, timeouts...
        return None, str(exc)


def _require_pillow() -> _PillowModule:
    if _pillow_module is None:
        raise RuntimeError("Pillow is required to convert downloaded icons")
    return _pillow_module


def open_rgba(data: bytes) -> _PillowImage:
    img = _require_pillow().open(io.BytesIO(data))
    return img.convert("RGBA")


def save_ico(img: _PillowImage, out: Path) -> None:
    """Square-crop/pad the image and save it as an ICO.

    The stored size is 32x32, or the source size when the source is already
    smaller than or equal to 32px.
    """
    w, h = img.size
    side = max(w, h)
    pillow = _require_pillow()
    canvas = pillow.new(mode="RGBA", size=(side, side), color=(0, 0, 0, 0))
    canvas.paste(img, ((side - w) // 2, (side - h) // 2))
    target = min(MAX_SIZE, side)
    if target < canvas.size[0]:
        canvas = canvas.resize((target, target), pillow.Resampling.LANCZOS)
    canvas.save(out, format="ICO", sizes=[(target, target)])


def has_pillow() -> bool:
    return _pillow_module is not None


def main() -> int:
    # Carry over icons that already succeeded, so re-runs only fill gaps.
    prev: dict[str, dict[str, object]] = {}
    if MANIFEST.exists():
        try:
            prev = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            prev = {}

    plugins = sorted(PLUGINS.glob("*.py"))
    usable_pil = has_pillow()
    manifest: dict[str, dict[str, object]] = {}

    for path in plugins:
        stem = path.stem
        ico_path = ICONS / f"{stem}.ico"
        if (
            ico_path.exists()
            and prev.get(stem, {}).get("ok")
            and prev.get(stem, {}).get("ico") == f"icons/{stem}.ico"
        ):
            manifest[stem] = prev[stem]
            continue
        entry: dict[str, object] = {
            "url": None,
            "host": "",
            "ico": f"icons/{stem}.ico",
            "ok": False,
            "error": None,
            "source": None,
        }
        manifest[stem] = entry

        url = extract_url(path)
        if url is None:
            entry["error"] = "no url class attribute found"
            continue
        entry["url"] = url
        host = (urlparse(url).hostname or "").lower()
        entry["host"] = host
        if not usable_pil:
            entry["error"] = "Pillow not available - run scripts/make_icons.py"
            continue

        data: bytes | None = None
        source: str | None = None
        errors: list[str] = []

        direct, err = fetch(f"https://{host}/favicon.ico")
        if err is not None:
            errors.append(f"direct: {err}")
        elif direct is None:
            errors.append("direct: empty response")
        else:
            try:
                _ = open_rgba(direct)  # validate it is a decodable image
                data, source = direct, "direct"
            except Exception as exc:
                errors.append(f"direct: not an image ({exc})")

        if data is None:
            gurl = f"https://www.google.com/s2/favicons?domain={host}&sz=64"
            goog, err = fetch(gurl)
            if err is not None:
                errors.append(f"google: {err}")
            elif goog is None:
                errors.append("google: empty response")
            else:
                try:
                    _ = open_rgba(goog)  # validate it is a decodable image
                    data, source = goog, "google"
                except Exception as exc:
                    errors.append(f"google: not an image ({exc})")

        if data is None and stem in EXTRA:
            wiki, err = fetch(EXTRA[stem])
            if err is not None:
                errors.append(f"wiki: {err}")
            elif wiki is None:
                errors.append("wiki: empty response")
            else:
                try:
                    _ = open_rgba(wiki)  # validate it is a decodable image
                    data, source = wiki, "wiki"
                except Exception as exc:
                    errors.append(f"wiki: not an image ({exc})")

        if data is None:
            durl = f"https://icons.duckduckgo.com/ip3/{host}.ico"
            duck, err = fetch(durl)
            if err is not None:
                errors.append(f"duckduckgo: {err}")
            elif duck is None:
                errors.append("duckduckgo: empty response")
            else:
                try:
                    dimg = open_rgba(duck)
                    if dimg.size[0] < 4 or dimg.size[1] < 4:
                        errors.append("duckduckgo: placeholder/blank image")
                    else:
                        data, source = duck, "duckduckgo"
                except Exception as exc:
                    errors.append(f"duckduckgo: not an image ({exc})")

        if data is None:
            horse_url = f"https://icon.horse/icon/{host}"
            horse, err = fetch(horse_url)
            if err is not None:
                errors.append(f"icon.horse: {err}")
            elif horse is None:
                errors.append("icon.horse: empty response")
            else:
                try:
                    horse_img = open_rgba(horse)
                    if horse_img.size[0] < 4 or horse_img.size[1] < 4:
                        errors.append("icon.horse: placeholder/blank image")
                    else:
                        data, source = horse, "icon.horse"
                except Exception as exc:
                    errors.append(f"icon.horse: not an image ({exc})")

        if data is None:
            entry["error"] = "; ".join(errors) or "no favicon"
            continue

        img = open_rgba(data)
        try:
            ICONS.mkdir(parents=True, exist_ok=True)
            save_ico(img, ICONS / f"{stem}.ico")
        except Exception as exc:
            entry["error"] = f"convert: {exc}"
            continue
        entry["ok"] = True
        entry["source"] = source

    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ok = sum(1 for v in manifest.values() if v["ok"])
    print(f"wrote {ok}/{len(manifest)} icons; manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
