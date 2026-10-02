"""Replay captured HTML through standalone engines without any network or profile access."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import logging
import random
import re
import shutil
import sys
import tempfile
import time
import tracemalloc
import urllib.parse
import urllib.request
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path
from threading import Lock
from types import ModuleType
from typing import NoReturn, Optional, Protocol, cast
from unittest.mock import patch

from test.engine_harness import load_qbitt_modules
from test.replay_transport import FixtureTransport, object_record

REPO_ROOT = Path(__file__).resolve().parent.parent


class SearchEngine(Protocol):
    def search(self, what: str, cat: str = "all") -> None: ...

    def parse_result(self, url: str) -> dict[str, object] | None: ...


class ModuleLoader(Protocol):
    def exec_module(self, module: ModuleType) -> None: ...


def usable_record(row: dict[str, object]) -> bool:
    """Recognize downloadable search rows, excluding error placeholders."""
    link, name = row.get("link"), row.get("name")
    if not isinstance(link, str) or not isinstance(name, str) or not name.strip():
        return False
    decoded = urllib.parse.unquote(link)
    if link.startswith("magnet:?"):
        hashes = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("xt", [])
        if not any(
            re.fullmatch(r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", h) for h in hashes
        ):
            return False
    elif not decoded.startswith(("http://", "https://")):
        return False
    if isinstance(row.get("size"), bool) or not isinstance(row.get("size"), (str, int, float)):
        return False
    for key in ("engine_url", "desc_link"):
        value = row.get(key)
        if key == "desc_link" and value is None:
            continue
        if not isinstance(value, str) or not value.startswith(("http://", "https://")):
            return False
    published = row.get("pub_date")
    if published is not None and (isinstance(published, bool) or not isinstance(published, int)):
        return False
    for key in ("seeds", "leech"):
        value = row.get(key)
        try:
            if isinstance(value, bool) or value is None:
                return False
            _ = int(str(value))
        except ValueError:
            return False
    return True


def replay(
    path: Path,
    *,
    source_root: Path | None = None,
    measure: bool = False,
    trace_allocations: bool = False,
) -> dict[str, object]:
    value = cast(object, json.loads(path.read_text(encoding="utf-8")))
    if not isinstance(value, dict):
        raise TypeError("parser case must be an object")
    case = cast(dict[str, object], value)
    plugin = case.get("plugin")
    query = case.get("query", "inception")
    category = case.get("category", "all")
    action = case.get("action", "search")
    root = REPO_ROOT
    catalog = object_record(
        cast(object, json.loads((root / "catalog" / "plugins.json").read_text())), "catalog"
    )
    entries = catalog.get("plugins")
    if not isinstance(entries, list):
        raise TypeError("catalog.plugins must be a list")
    ids = {object_record(item, "catalog entry").get("id") for item in cast(list[object], entries)}
    if not isinstance(plugin, str) or not re.fullmatch(r"[a-z0-9_]+", plugin) or plugin not in ids:
        raise ValueError("unsupported fixture plugin")
    if not isinstance(query, str) or not isinstance(category, str):
        raise TypeError("query and category must be strings")
    if action not in ("search", "detail", "download") or (
        action == "detail" and plugin != "elitetorrent"
    ):
        raise ValueError("unsupported fixture action")
    limits: dict[str, int] = {}
    for key, default, maximum in (("maxPages", 2, 30), ("maxDetails", 5, 100)):
        limit = case.get(key, default)
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= maximum:
            raise ValueError(f"invalid {key}")
        limits[key] = limit

    worker_limit = case.get("maxWorkers")
    if worker_limit is not None and (
        not isinstance(worker_limit, int)
        or isinstance(worker_limit, bool)
        or not 1 <= worker_limit <= 16
    ):
        raise ValueError("invalid maxWorkers")
    deadline_ms = case.get("deadlineMs")
    if deadline_ms is not None and (
        not isinstance(deadline_ms, int)
        or isinstance(deadline_ms, bool)
        or not 0 <= deadline_ms <= 60000
    ):
        raise ValueError("invalid deadlineMs")

    raw_downloads = case.get("verifiedDownloads", [])
    if not isinstance(raw_downloads, list) or not all(
        isinstance(url, str) for url in cast(list[object], raw_downloads)
    ):
        raise TypeError("verifiedDownloads must be a list of URLs")
    verified_downloads = set(cast(list[str], raw_downloads))
    download_requests: list[str] = []
    output = io.StringIO()
    records: list[dict[str, object]] = []
    result_request_counts: list[int] = []
    errors: list[str] = []
    lock = Lock()
    transport = FixtureTransport(case, errors)
    started = 0.0
    first_result: float | None = None
    result_times: list[float] = []
    executors: list[ThreadPoolExecutor] = []

    class ReplayExecutor(ThreadPoolExecutor):
        def __init__(self, max_workers: int | None = None) -> None:
            super().__init__(max_workers=max_workers)
            executors.append(self)

    class ReplayLogHandler(logging.NullHandler):
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            super().__init__()

    def opener_open(
        opener: urllib.request.OpenerDirector,
        url: str | urllib.request.Request,
        data: bytes | None = None,
        timeout: object = None,
    ) -> object:
        _ = timeout
        if isinstance(url, str):
            url = urllib.request.Request(url, headers=dict(opener.addheaders))
        return transport.urlopen(url, data)

    def printer(row: object) -> None:
        nonlocal first_result
        with lock:
            if not isinstance(row, dict):
                errors.append("result is not a dictionary")
                return
            record = cast(dict[str, object], row).copy()
            records.append(record)
            result_request_counts.append(len(transport.requests))
            if measure and usable_record(record):
                elapsed = time.perf_counter() - started
                result_times.append(elapsed)
                if first_result is None:
                    first_result = elapsed

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
    vars(sys.modules["helpers"]).update(
        {"retrieve_url": transport.retrieve, "download_file": download}
    )
    vars(sys.modules["novaprinter"])["prettyPrinter"] = printer
    plugin_path = (
        (source_root or Path(__file__).resolve().parent.parent) / "plugins" / f"{plugin}.py"
    )
    source = plugin_path.read_bytes()
    actual_hash = hashlib.sha256(source).hexdigest()
    source_hash = case.get("sourceSha256")
    if source_hash is not None and source_hash != actual_hash:
        raise ValueError("plugin source changed after response capture")
    metrics: dict[str, object] = {}
    with (
        tempfile.TemporaryDirectory(prefix="qbsearch-replay-") as directory,
        patch("socket.socket.connect", forbidden),
        patch("socket.socket.connect_ex", forbidden),
        patch("socket.create_connection", forbidden),
        patch("socket.getaddrinfo", forbidden),
        patch("urllib.request.urlopen", transport.urlopen),
        patch("urllib.request.OpenerDirector.open", opener_open),
        patch("concurrent.futures.ThreadPoolExecutor", ReplayExecutor),
        patch("logging.FileHandler", ReplayLogHandler),
        patch.object(Path, "home", return_value=Path(directory) / "home"),
        redirect_stdout(output),
    ):
        # Copy every engine into its own disposable profile. Import-time config,
        # cookies, icons, and log paths must never touch the repository or qBittorrent.
        isolated_path = Path(directory) / "plugins" / f"{plugin}.py"
        isolated_path.parent.mkdir()
        _ = shutil.copyfile(plugin_path, isolated_path)
        spec = importlib.util.spec_from_file_location(plugin, isolated_path)
        if spec is None or spec.loader is None:
            raise ValueError("cannot load plugin")
        module = importlib.util.module_from_spec(spec)
        sys.modules[plugin] = module
        random.seed(0)
        logging.getLogger().addHandler(logging.NullHandler())
        if trace_allocations:
            tracemalloc.start()
        started = time.perf_counter()
        cpu_started = time.process_time()
        # Python 3.9's abstract Loader stub omits the concrete exec_module API.
        cast(ModuleLoader, cast(object, spec.loader)).exec_module(module)
        import_seconds = time.perf_counter() - started
        import_cpu = time.process_time() - cpu_started
        vars(module).update({"MAX_PAGES": limits["maxPages"], "MAX_DETAILS": limits["maxDetails"]})
        if worker_limit is not None:
            vars(module)["MAX_WORKERS"] = worker_limit
        if isinstance(deadline_ms, int):
            vars(module)["SEARCH_DEADLINE"] = deadline_ms / 1000
        # Missing fixture responses still exercise retries, without artificial sleeps.
        vars(module)["RETRY_DELAY"] = 0
        cache_xml = case.get("cacheXml")
        if cache_xml is not None:
            if plugin != "academictorrents" or not isinstance(cache_xml, str):
                raise ValueError("cacheXml is only supported for AcademicTorrents")
            cache = cast(Path, vars(module)["cache_path"])
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache_date = str(date.today()) if case.get("cacheFresh", True) else "2000-01-01"
            _ = cache.write_text(f"{cache_date}\n{cache_xml}", encoding="utf-8")
            # Fixture setup is excluded from the engine's CPU/time/allocation metrics.
            started = time.perf_counter() - import_seconds
            cpu_started = time.process_time() - import_cpu
            if trace_allocations:
                tracemalloc.reset_peak()
        factory = cast(Callable[[], SearchEngine], getattr(module, str(plugin)))
        try:
            engine = factory()
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
                repeat = case.get("repeatSearches", 1)
                if not isinstance(repeat, int) or isinstance(repeat, bool) or not 1 <= repeat <= 3:
                    raise ValueError("repeatSearches must be an integer from 1 to 3")
                for _ in range(repeat):
                    factory().search(query, category)
        except Exception as error:
            errors.append(f"{type(error).__name__}: {error}")
        finally:
            # Keep fixture transports and profile guards installed until canceled
            # searches' already-running workers have finished their bounded I/O.
            for executor in executors:
                executor.shutdown(wait=True)
            if measure:
                metrics = {
                    "importSeconds": import_seconds,
                    "firstResultSeconds": first_result,
                    "totalSeconds": time.perf_counter() - started,
                    "cpuSeconds": time.process_time() - cpu_started,
                    "resultTimesSeconds": result_times,
                    "responseBytes": transport.response_bytes,
                    "usableResults": sum(usable_record(row) for row in records),
                    "peakAllocatedBytes": None,
                    "peakRssBytes": None,
                }
                if trace_allocations:
                    _, peak = tracemalloc.get_traced_memory()
                    metrics["peakAllocatedBytes"] = peak
                try:
                    import resource

                    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                    metrics["peakRssBytes"] = rss if sys.platform == "darwin" else rss * 1024
                except ImportError:
                    pass
            if trace_allocations:
                tracemalloc.stop()
    return {
        "plugin": plugin,
        "records": records,
        "requests": transport.requests,
        "requestDetails": transport.request_details,
        "resultRequestCounts": result_request_counts,
        "errors": errors,
        "downloadRequests": download_requests,
        "output": output.getvalue().splitlines(),
        "peakConcurrentRequests": transport.peak,
        "requestConcurrency": transport.request_concurrency,
        "sourceSha256": actual_hash,
        "python": sys.version.split()[0],
        "metrics": metrics,
    }


def main() -> int:
    try:
        import argparse

        parser = argparse.ArgumentParser(description=__doc__)
        _ = parser.add_argument("case")
        _ = parser.add_argument("--source-root", type=Path)
        _ = parser.add_argument("--measure", action="store_true")
        _ = parser.add_argument("--trace", action="store_true")
        args = parser.parse_args()
        report = replay(
            Path(cast(str, args.case)),
            source_root=cast(Optional[Path], args.source_root),
            measure=cast(bool, args.measure),
            trace_allocations=cast(bool, args.trace),
        )
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
