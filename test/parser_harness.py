"""Replay captured HTML through standalone engines without any network or profile access."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import time
from collections.abc import Callable
from contextlib import redirect_stdout
from pathlib import Path
from threading import Lock
from types import ModuleType
from typing import NoReturn, Protocol, cast
from unittest.mock import patch

from test.engine_harness import load_qbitt_modules


class SearchEngine(Protocol):
    def search(self, what: str, cat: str = "all") -> None: ...

    def parse_result(self, url: str) -> dict[str, object] | None: ...


class ModuleLoader(Protocol):
    def exec_module(self, module: ModuleType) -> None: ...


def replay(path: Path) -> dict[str, object]:
    value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise TypeError("parser case must be an object")
    case = cast(dict[str, object], value)
    plugin = case.get("plugin")
    query = case.get("query", "inception")
    category = case.get("category", "all")
    action = case.get("action", "search")
    if plugin not in (
        "elitetorrent",
        "bitsearch",
        "solidtorrents",
        "ali213",
        "pirateiro",
        "traht",
        "audiobookbay",
        "darklibria",
        "yts",
    ):
        raise ValueError("unsupported fixture plugin")
    if not isinstance(query, str) or not isinstance(category, str):
        raise TypeError("query and category must be strings")
    if action not in ("search", "detail", "download") or (
        action == "detail" and plugin != "elitetorrent"
    ):
        raise ValueError("unsupported fixture action")
    raw_responses = case.get("responses")
    if not isinstance(raw_responses, dict):
        raise TypeError("responses must map URLs to HTML strings")
    response_values = cast(dict[object, object], raw_responses)
    responses: dict[str, str] = {}
    for url, html in response_values.items():
        if not isinstance(url, str) or not isinstance(html, str):
            raise TypeError("responses must map URLs to HTML strings")
        responses[url] = html

    limits: dict[str, int] = {}
    for key, default, maximum in (("maxPages", 2, 30), ("maxDetails", 5, 100)):
        limit = case.get(key, default)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= maximum:
            raise ValueError(f"invalid {key}")
        limits[key] = limit

    delay_ms = case.get("responseDelayMs", 0)
    if not isinstance(delay_ms, int) or isinstance(delay_ms, bool) or not 0 <= delay_ms <= 1000:
        raise ValueError("invalid responseDelayMs")

    worker_limit = case.get("maxWorkers")
    if worker_limit is not None and (
        not isinstance(worker_limit, int)
        or isinstance(worker_limit, bool)
        or not 1 <= worker_limit <= 16
    ):
        raise ValueError("invalid maxWorkers")

    raw_downloads = case.get("verifiedDownloads", [])
    if not isinstance(raw_downloads, list) or not all(
        isinstance(url, str) for url in cast(list[object], raw_downloads)
    ):
        raise TypeError("verifiedDownloads must be a list of URLs")
    verified_downloads = set(cast(list[str], raw_downloads))
    download_requests: list[str] = []
    output = io.StringIO()
    records: list[dict[str, object]] = []
    requests: list[str] = []
    errors: list[str] = []
    lock = Lock()
    active_requests = 0
    peak_concurrent_requests = 0
    request_concurrency: list[int] = []

    def retrieve(url: str, *_args: object, **_kwargs: object) -> str:
        nonlocal active_requests, peak_concurrent_requests
        with lock:
            active_requests += 1
            peak_concurrent_requests = max(peak_concurrent_requests, active_requests)
            requests.append(url)
            request_concurrency.append(active_requests)
            if url not in responses:
                errors.append(f"unexpected request: {url}")
        try:
            if delay_ms:
                time.sleep(delay_ms / 1000)
            return responses.get(url, "")
        finally:
            with lock:
                active_requests -= 1

    def printer(row: object) -> None:
        with lock:
            if not isinstance(row, dict):
                errors.append("result is not a dictionary")
                return
            records.append(cast(dict[str, object], row).copy())

    def forbidden(*_args: object, **_kwargs: object) -> NoReturn:
        with lock:
            errors.append("network or download attempted during offline replay")
        raise RuntimeError("network and downloads are forbidden during offline replay")

    def download(url: str) -> str:
        if action != "download":
            forbidden()
        with lock:
            download_requests.append(url)
            if url not in verified_downloads:
                errors.append(f"unverified torrent download: {url}")
                return ""
        # Bun validates real metadata separately. No file is written or installed here.
        return f"/offline/verified.torrent {url}"

    # Always use stubs, even on a machine with a real qBittorrent profile.
    _ = load_qbitt_modules(prefer_profile=False)
    vars(sys.modules["helpers"]).update({"retrieve_url": retrieve, "download_file": download})
    vars(sys.modules["novaprinter"])["prettyPrinter"] = printer
    plugin_path = Path(__file__).resolve().parent.parent / "plugins" / f"{plugin}.py"
    source_hash = case.get("sourceSha256")
    if (
        source_hash is not None
        and source_hash != hashlib.sha256(plugin_path.read_bytes()).hexdigest()
    ):
        raise ValueError("plugin source changed after response capture")
    spec = importlib.util.spec_from_file_location(str(plugin), plugin_path)
    if spec is None:
        raise ValueError("cannot load plugin")
    loader = cast(object, spec.loader)
    if loader is None:
        raise ValueError("cannot load plugin")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve postponed annotations through the registered module.
    sys.modules[str(plugin)] = module
    with (
        patch("socket.socket.connect", forbidden),
        patch("socket.socket.connect_ex", forbidden),
        patch("socket.create_connection", forbidden),
        patch("socket.getaddrinfo", forbidden),
        patch("urllib.request.urlopen", forbidden),
        redirect_stdout(output),
    ):
        # Python 3.9's abstract Loader stub omits the concrete exec_module API.
        cast(ModuleLoader, loader).exec_module(module)
        vars(module).update({"MAX_PAGES": limits["maxPages"], "MAX_DETAILS": limits["maxDetails"]})
        if worker_limit is not None:
            vars(module)["MAX_WORKERS"] = worker_limit
        # Missing fixture responses still exercise retries, without artificial sleeps.
        vars(module)["RETRY_DELAY"] = 0
        factory = cast(Callable[[], SearchEngine], getattr(module, str(plugin)))
        engine = factory()
        try:
            if action == "download":
                detail_url = case.get("detailUrl")
                if not isinstance(detail_url, str):
                    raise ValueError("download action requires detailUrl")
                method = getattr(engine, "download_torrent", None)
                if callable(method):
                    cast(Callable[[str], None], method)(detail_url)
                else:
                    print(download(detail_url))
            elif action == "detail":
                detail_url = case.get("detailUrl")
                if not isinstance(detail_url, str):
                    raise ValueError("detail action requires detailUrl")
                row = engine.parse_result(detail_url)
                if row is not None:
                    printer(row)
            else:
                engine.search(query, category)
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
    return {
        "plugin": plugin,
        "records": records,
        "requests": requests,
        "errors": errors,
        "downloadRequests": download_requests,
        "output": output.getvalue().splitlines(),
        "peakConcurrentRequests": peak_concurrent_requests,
        "requestConcurrency": request_concurrency,
    }


def main() -> int:
    try:
        if len(sys.argv) != 2:
            raise ValueError("expected one parser-case JSON path")
        report = replay(Path(sys.argv[1]))
    except Exception as error:
        report = {
            "records": [],
            "requests": [],
            "downloadRequests": [],
            "output": [],
            "errors": [f"{type(error).__name__}: {error}"],
        }
    print(json.dumps(report))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
