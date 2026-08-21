#!/usr/bin/env python3
"""Run one plugin's search against its configured remote service.

The parent runner starts this script in an isolated subprocess.  The plugin is
loaded with qBittorrent's nova3 modules when they are available, its search is
invoked, and qBittorrent result records are captured instead of printed.
"""

from __future__ import annotations

import argparse
import contextlib
import gzip
import html
import importlib
import importlib.machinery
import importlib.util
import io
import os
import socket
import ssl
import sys
import tempfile
import threading
import traceback
import types
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import NamedTuple, Protocol, TypedDict, Union, cast

ROOT = Path(__file__).resolve().parents[1]
LIVE_TIMEOUT = 20.0
REQUIRED_RESULT_FIELDS = ("link", "name", "size", "seeds", "leech", "engine_url")


class SearchResult(TypedDict, total=False):
    link: str
    name: str
    size: float | int | str
    seeds: int
    leech: int
    engine_url: str
    desc_link: str
    pub_date: int


class _HTTPResponse(Protocol):
    def read(self) -> bytes: ...

    def getheader(self, name: str, default: str = "") -> str | None: ...


class _HTTPResponseContext(Protocol):
    def __enter__(self) -> _HTTPResponse: ...

    def __exit__(self, *args: object) -> bool: ...


class _Plugin(Protocol):
    def search(self, what: str, category: str) -> object: ...


class _Harness(Protocol):
    def ensure_qbitt_python(self) -> None: ...

    def load_qbitt_modules(self) -> bool: ...


class Arguments(NamedTuple):
    plugin: Path
    query: str
    category: str
    allow_empty: bool


def _fallback_helpers() -> None:
    """Install live stdlib adapters when qBittorrent is not installed."""
    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0"
        )
    }

    def retrieve_url(
        url: str,
        custom_headers: Mapping[str, str] | None = None,
        request_data: bytes | None = None,
        ssl_context: ssl.SSLContext | None = None,
        unescape_html_entities: bool = True,
    ) -> str:
        request = urllib.request.Request(
            url,
            request_data,
            {**headers, **(dict(custom_headers) if custom_headers else {})},
        )
        try:
            with cast(
                _HTTPResponseContext,
                urllib.request.urlopen(request, timeout=LIVE_TIMEOUT, context=ssl_context),
            ) as response:
                data: bytes = response.read()
                if data[:2] == b"\x1f\x8b":
                    with (
                        io.BytesIO(data) as compressed,
                        gzip.GzipFile(fileobj=compressed) as decompressor,
                    ):
                        data = decompressor.read()
                charset = "utf-8"
                content_type = response.getheader("Content-Type", "") or ""
                if "charset=" in content_type:
                    charset = content_type.split("charset=", 1)[1].split(";", 1)[0]
                text = data.decode(charset, "replace")
                return html.unescape(text) if unescape_html_entities else text
        except urllib.error.URLError as error:
            print(f"Connection error: {error}", file=sys.stderr)
            return ""
        return ""

    def download_file(
        url: str,
        referer: str | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> str:
        request = urllib.request.Request(url, headers=headers)
        if referer is not None:
            request.add_header("referer", referer)
        data: bytes = b""
        with cast(
            _HTTPResponseContext,
            urllib.request.urlopen(request, timeout=LIVE_TIMEOUT, context=ssl_context),
        ) as response:
            data = response.read()
        file_descriptor, path = tempfile.mkstemp()
        with os.fdopen(file_descriptor, "wb") as output:
            _ = output.write(data)
        return f"{path} {url}"

    novaprinter = types.ModuleType("novaprinter")

    def any_size_to_bytes(value: object) -> object:
        return value

    def ignore_result(_result: object) -> None:
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

    helpers = types.ModuleType("helpers")

    def no_op(*_args: object, **_kwargs: object) -> None:
        return None

    vars(helpers).update(
        {
            "_headers": headers,
            "retrieve_url": retrieve_url,
            "download_file": download_file,
            "enable_socks_proxy": no_op,
            "htmlentitydecode": html.unescape,
        }
    )

    socks = types.ModuleType("socks")
    vars(socks).update(
        {
            "PROXY_TYPE_SOCKS4": 1,
            "PROXY_TYPE_SOCKS5": 2,
            "socksocket": socket.socket,
            "setdefaultproxy": no_op,
            "set_default_proxy": no_op,
        }
    )

    sys.modules["novaprinter"] = novaprinter
    sys.modules["helpers"] = helpers
    sys.modules["socks"] = socks


def _prepare_qbittorrent_modules() -> bool:
    """Load qBittorrent modules or install adapters that still use the network."""
    sys.path.insert(0, str(ROOT))
    harness = cast(_Harness, cast(object, importlib.import_module("test_engines")))
    harness.ensure_qbitt_python()
    using_real = harness.load_qbitt_modules()
    if not using_real:
        _fallback_helpers()
    return using_real


def _load_plugin(path: Path) -> tuple[types.ModuleType, type[_Plugin]]:
    stem = path.stem
    spec = importlib.util.spec_from_file_location(stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[stem] = module
    loader = spec.loader
    if not isinstance(loader, importlib.machinery.SourceFileLoader):
        raise TypeError(f"unexpected loader type {type(loader)!r}")
    loader.exec_module(module)
    raw_engine_class = getattr(module, stem, None)
    if raw_engine_class is None:
        raise AttributeError(f"class/alias '{stem}' not found")
    engine_class = cast(type[_Plugin], raw_engine_class)
    return module, engine_class


def _install_result_capture() -> tuple[list[object], threading.Lock]:
    novaprinter = importlib.import_module("novaprinter")
    results: list[object] = []
    lock = threading.Lock()

    def capture(result: object) -> None:
        with lock:
            results.append(result)

    vars(novaprinter)["prettyPrinter"] = capture
    return results, lock


def _install_network_counter() -> list[int]:
    count = [0]
    lock = threading.Lock()
    original_open = cast(Callable[..., object], urllib.request.OpenerDirector.open)

    def counted_open(opener: urllib.request.OpenerDirector, *args: object, **kwargs: object):
        with lock:
            count[0] += 1
        return original_open(opener, *args, **kwargs)

    type.__setattr__(urllib.request.OpenerDirector, "open", counted_open)
    return count


def _validate_results(results: list[object]) -> str | None:
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            return f"result {index} is not a mapping"
        missing = [field for field in REQUIRED_RESULT_FIELDS if field not in result]
        if missing:
            return f"result {index} is missing fields: {', '.join(missing)}"
    return None


def parse_args() -> Arguments:
    parser = argparse.ArgumentParser(description="Run one qBittorrent plugin live.")
    _ = parser.add_argument("plugin", type=Path)
    _ = parser.add_argument("--query", default="ubuntu")
    _ = parser.add_argument("--category", default="all")
    _ = parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="allow a completed live search with zero parsed result records",
    )
    parsed = parser.parse_args()
    return Arguments(
        plugin=cast(Path, parsed.plugin),
        query=cast(str, parsed.query),
        category=cast(str, parsed.category),
        allow_empty=cast(bool, parsed.allow_empty),
    )


def main() -> int:
    args = parse_args()
    path = args.plugin.resolve()
    results: list[object] = []
    request_count = [0]
    try:
        using_real = _prepare_qbittorrent_modules()
        results, _ = _install_result_capture()
        request_count = _install_network_counter()
        _, engine_class = _load_plugin(path)
        engine = engine_class()
        captured_stdout = io.StringIO()
        encoded_query = urllib.parse.quote(args.query)
        with contextlib.redirect_stdout(captured_stdout):
            _ = engine.search(encoded_query, args.category)
        result_error = _validate_results(results)
        if result_error:
            raise ValueError(result_error)
        if request_count[0] == 0:
            raise RuntimeError("search completed without an observed HTTP request")
        if not results and not args.allow_empty:
            raise RuntimeError(
                "live search completed but produced no result records "
                + "(use --allow-empty to accept this)"
            )
        module_mode = "qBittorrent modules" if using_real else "stdlib live adapters"
        print(
            f"LIVE PASS {path.stem} [{args.query!r}]: {len(results)} results, "
            + f"{request_count[0]} HTTP requests, {module_mode}"
        )
        return 0
    except BaseException as error:
        print(
            f"LIVE FAIL {path.stem} [{args.query!r}]: {type(error).__name__}: {error}; "
            + f"{len(results)} results, {request_count[0]} HTTP requests",
            file=sys.stderr,
        )
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
