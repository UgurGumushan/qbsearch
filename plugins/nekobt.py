# VERSION: 1.0
"""
NekoBT anime torrent search. Queries the site's JSON API; each torrent's link
is its magnet when present, else built from the infohash, falling back to the
torrent download endpoint.
"""

from __future__ import annotations

import json
import urllib.parse
from typing import ClassVar, TypedDict, cast
from urllib import request

from novaprinter import SearchResults, prettyPrinter

_qbt_helper_retrieve_url = None
# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = 4
SEARCH_DEADLINE = 60.0
MAX_PAGES = 30
MAX_DETAILS = 100

_qbt_socket.setdefaulttimeout(HTTP_TIMEOUT)
_QBT_RETRYABLE_HTTP_STATUS = frozenset((408, 425, 429, 500, 502, 503, 504))
_qbt_search_deadline = None


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status = 200
    code = 200

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *args, **kwargs) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, name: str, default: object = None):
        return default

    def info(self):
        return self

    def get(self, name: str, default: object = None):
        return default


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result = operation()
            if isinstance(result, str) and result:
                return result
            if result not in (None, "", b""):
                return str(result)
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return ""
            try:
                error.close()
            except Exception:
                pass
        except Exception:
            pass
        if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
            _qbt_sleep(attempt)
    return ""


def _qbt_safe_urlopen(url, data=None, *, context=None):
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _QBTEmptyResponse(url)
        response = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status is not None and status >= 400:
                response.close()
                return _QBTEmptyResponse(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _QBTEmptyResponse(url)
            try:
                error.close()
            except Exception:
                pass
        except (_QBTTransientHTTPError, OSError, EOFError, TimeoutError):
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
        except Exception:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass
            # A malformed request is not useful to retry, but it must not
            # abort the qBittorrent search process.
            return _QBTEmptyResponse(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _QBTEmptyResponse(url)


_qbt_retrieve_url = _qbt_helper_retrieve_url


def retrieve_url(*args, **kwargs) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        prettyPrinter(result)


def _qbt_run_parallel(worker, jobs, deadline=None):
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results = []
    try:
        remaining = max(0.0, deadline - _qbt_time.monotonic())
        for future in _qbt_as_completed(futures, timeout=remaining):
            try:
                results.append(future.result())
            except Exception:
                # One dead site/detail page must not discard other results.
                pass
    except _qbt_FuturesTimeoutError:
        for future in futures:
            future.cancel()
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# END GENERATED QBITT SAFETY PREAMBLE


class TorrentItem(TypedDict, total=False):
    id: int
    title: str
    auto_title: str
    filesize: int | float | str
    seeders: int
    leechers: int
    uploaded_at: int | float | str
    created_at: int | float | str
    magnet: str
    infohash: str


class ApiData(TypedDict, total=False):
    results: list[TorrentItem]
    torrents: list[TorrentItem]


class ApiResponse(TypedDict, total=False):
    data: ApiData | list[TorrentItem]


class nekobt:
    url = "https://nekobt.to/"
    name = "NekoBT"

    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    def format_size(self, size_bytes: float | str) -> str:
        try:
            size_bytes = float(size_bytes)
            for unit in ["B", "KB", "MB", "GB", "TB"]:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except Exception:
            return "0 MB"

    def search(self, what: str, cat: str = "all"):
        what = urllib.parse.unquote(what)
        query = urllib.parse.quote_plus(what)

        search_url = f"{self.url}api/v1/torrents/search?query={query}"

        try:
            req = request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) qBittorrent Search",
                    "Accept": "application/json",
                },
            )
            with _qbt_safe_urlopen(req) as response:
                data: ApiResponse | list[TorrentItem] = json.loads(
                    response.read().decode("utf-8", errors="ignore")
                )

            # The API wraps the list in "data", sometimes under "results"
            # or "torrents"; it may also answer with a bare list.
            torrents: list[TorrentItem] = []
            if isinstance(data, dict):
                res_data: object = data.get("data", [])
                if isinstance(res_data, list):
                    torrents = cast(list[TorrentItem], res_data)
                elif isinstance(res_data, dict):
                    nested: object = res_data.get("results")
                    if not isinstance(nested, list):
                        nested = res_data.get("torrents")
                    if isinstance(nested, list):
                        torrents = cast(list[TorrentItem], nested)
            else:
                torrents = data

            if not torrents:
                print("Error: No se encontraron resultados o la palabra buscada no existe.")
                return

            for item in torrents:
                torrent_id = item.get("id")

                # Use the title; fall back to auto_title when it is empty
                name_value = item.get("title")
                if isinstance(name_value, str) and name_value:
                    name = name_value
                else:
                    auto_title = item.get("auto_title")
                    name = auto_title if isinstance(auto_title, str) and auto_title else "Desconocido"

                size_value = item.get("filesize")
                if isinstance(size_value, (int, float)):
                    size: float | str = float(size_value)
                elif isinstance(size_value, str):
                    size = size_value
                else:
                    size = 0.0

                seeds = item.get("seeders", 0)
                leech = item.get("leechers", 0)

                pub_date: int = -1
                # uploaded_at / created_at arrive as millisecond-epoch strings
                created_at: int | float | str | None = item.get("uploaded_at")
                if created_at is None:
                    created_at = item.get("created_at")
                if created_at:
                    try:
                        # Convert to a second-epoch timestamp
                        pub_date = int(float(created_at) / 1000)
                    except Exception:
                        pass

                # Magnet is provided directly by the API when available
                magnet = item.get("magnet", "")
                if magnet:
                    download_link = magnet
                else:
                    infohash = item.get("infohash")
                    if infohash:
                        download_link = (
                            f"magnet:?xt=urn:btih:{infohash}&dn={urllib.parse.quote(name)}"
                        )
                    else:
                        download_link = f"{self.url}api/v1/torrents/download/{torrent_id}"

                desc_link = f"{self.url}torrents/{torrent_id}"

                res: SearchResults = {
                    "engine_url": self.url,
                    "name": name,
                    "size": self.format_size(size),
                    "seeds": int(seeds),
                    "leech": int(leech),
                    "link": download_link,
                    "desc_link": desc_link,
                    "pub_date": pub_date,
                }
                _qbt_prettyPrinter(res)

        except Exception as e:
            print(f"Error procesando la búsqueda: {e}")
