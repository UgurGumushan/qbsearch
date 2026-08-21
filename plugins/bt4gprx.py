# VERSION: 2.0
"""bt4gprx engine: movies, TV, music, books and software torrents.

Download links are redirects through a third-party domain, so the engine
follows each one and rebuilds a magnet from the torrent hash plus a public
tracker list.
"""
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin

from helpers import retrieve_url as _qbt_helper_retrieve_url  # noqa: F401
from novaprinter import SearchResults, prettyPrinter

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


_qbt_retrieve_url = globals().get("_qbt_helper_retrieve_url")


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


class bt4gprx:
    url = "https://bt4gprx.com/"
    name = "bt4gprx"
    supported_categories: ClassVar[dict[str, str]]  = {'all': '', 'movies': 'movie/', 'tv': 'movie/', 'music': 'audio/', 'books': 'doc/', 'software': 'app/'}

    def __init__(self):
        self.trackerlist: list[str] = []

    class MyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.is_in_container = False
            self.is_in_entry = False
            self.b_value = ""
            self.container_row_count = 0
            self.temp_result: dict[str, str] = {}
            self.results: list[dict[str, str]] = []

        def parse(self, feed: str) -> list[dict[str, str]]:
            super().feed(feed)
            return self.results

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, str | None]]
        ) -> None:
            attr_dict = {key: value for key, value in attrs if value is not None}
            if tag == "div":
                if not self.is_in_container and attr_dict.get("class", "") == "container":
                    self.is_in_container = True
            elif tag == "a":
                if self.is_in_container and all(x in attr_dict for x in ["title", "href"]):
                    self.is_in_entry = True
                    self.temp_result.update(attr_dict)
            elif tag == "b" and self.is_in_entry:
                classname = attr_dict.get("class") or ""
                idname = attr_dict.get("id") or ""
                self.b_value = "filesize" if "cpill" in classname else idname

        def handle_endtag(self, tag: str) -> None:
            if tag == "div":
                self.is_in_entry = False

        def handle_data(self, data: str) -> None:
            if self.b_value != "":
                self.temp_result[self.b_value] = data
                if self.b_value == "leechers":
                    self.results.append(self.temp_result)
                    self.temp_result = {}
                self.b_value = ""

    def search(self, term: str, cat: str = "all") -> None:
        pagenumber = 1
        all_results: list[dict[str, str]] = []
        for _ in range(MAX_PAGES):
            result_page = self.search_page(term, pagenumber, cat)
            if result_page:
                all_results.extend(result_page)
            else:
                break
            pagenumber = pagenumber + 1
        self.pretty_print_results(all_results)

    def search_page(self, term: str, pagenumber: int, cat: str) -> list[dict[str, str]]:
        try:
            query = f"{self.url}{self.supported_categories[cat]}search/{term}/byseeders/{pagenumber}"
            parser = self.MyHTMLParser()
            return parser.parse(retrieve_url(query))
        except Exception:
            return []

    def download_torrent(self, info: str) -> str | None:
        try:
            content = retrieve_url(info)
            match = re.search(r'href="//(downloadtorrentfile.com/hash/[^"]+)', content)
            if not match:
                print("Failed to find downloadtorrentfile.com link.")
                return
            actual_link = "https:" + match.group(0)
        except Exception as e:
            print(f"Error extracting downloadtorrentfile.com link: {e}")
            return
        try:
            hash_value = actual_link.split("/hash/")[1].split("?")[0]
            name_value = actual_link.split("?name=")[1]
        except Exception as e:
            print(f"Error extracting hash and name: {e}")
            return
        if not self.trackerlist:
            self.trackerlist = json.loads(retrieve_url("https://downloadtorrentfile.com/trackerlist"))
        magnet = f"magnet:?xt=urn:btih:{hash_value}&dn={name_value}&tr=" + "&tr=".join(self.trackerlist)
        return magnet

    def pretty_print_results(self, results: list[dict[str, str]]) -> None:
        sorted_results = sorted(results, key=lambda x: int(x['seeders']), reverse=True)
        for result in sorted_results:
            magnet_link = self.download_torrent(urljoin(self.url, result['href']))
            temp_result: SearchResults = {
                'name': result['title'],
                'size': result['filesize'],
                'seeds': int(result['seeders']),
                'leech': int(result['leechers']),
                'engine_url': self.url,
                'link': magnet_link or '',
            }
            _qbt_prettyPrinter(temp_result)
