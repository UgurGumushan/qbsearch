# VERSION: 0.4
"""AudioBook Bay engine: audiobook torrent search.

The site moves between mirror domains, so a healthy base URL is probed
first; magnets are then built from the info hash found on each book page.
"""

from __future__ import annotations

import urllib.parse
from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
    from types import TracebackType as _QBTTracebackType
    from typing import TYPE_CHECKING
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

if TYPE_CHECKING:
    from typing_extensions import override
else:

    def override(function: _QBTCallable[..., object]) -> _QBTCallable[..., object]:
        return function


HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = 4
SEARCH_DEADLINE = 60.0
MAX_PAGES = 30
MAX_DETAILS = 100

_qbt_socket.setdefaulttimeout(HTTP_TIMEOUT)
_QBT_RETRYABLE_HTTP_STATUS = frozenset((408, 425, 429, 500, 502, 503, 504))
_qbt_search_deadline: float | None = None
_QBTJobResult = _QBTTypeVar("_QBTJobResult")


class _QBTResponse(_QBTProtocol):
    status: int | None

    def close(self) -> None: ...

    def read(self, *args: object, **kwargs: object) -> bytes: ...

    def getcode(self) -> int: ...

    def geturl(self) -> str: ...

    def getheader(self, name: str, default: object = None) -> object: ...

    def info(self) -> _QBTResponse: ...

    def get(self, name: str, default: object = None) -> object: ...


class _QBTResponseContext(_QBTResponse, _QBTProtocol):
    def __enter__(self) -> _QBTResponse: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool: ...


_qbt_urlopen_typed = _qbt_cast(_QBTCallable[..., _QBTResponseContext], _qbt_urlopen)


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status: int | None = 200
    code: int = 200
    _url: str

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: _QBTTracebackType | None,
    ) -> bool:
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, _name: str, default: object = None) -> object:
        return default

    def info(self) -> _QBTResponse:
        return _qbt_cast(_QBTResponse, _qbt_cast(object, self))

    def get(self, _name: str, default: object = None) -> object:
        return default


def _qbt_empty_response(url: object) -> _QBTResponseContext:
    return _qbt_cast(_QBTResponseContext, _qbt_cast(object, _QBTEmptyResponse(url)))


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result: object = operation()
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


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen_typed(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _qbt_empty_response(url)
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
            return _qbt_empty_response(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _qbt_empty_response(url)


_qbt_retrieve_url = _qbt_cast(_QBTCallable[..., object], _qbt_helper_retrieve_url)


def retrieve_url(*args: object, **kwargs: object) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result: object) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        printer = _qbt_cast(_QBTCallable[[object], None], prettyPrinter)
        printer(result)


def _qbt_run_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
) -> list[_QBTJobResult]:
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures: list[_QBTFuture[_QBTJobResult]] = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results: list[_QBTJobResult] = []
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
            _ = future.cancel()
    finally:
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            _ = executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# These hooks are available to standalone engines even when a particular
# engine does not call every optional adapter directly.
__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


# Raised when the book page we follow does not actually contain the torrent.
class NotFoundError(Exception):
    pass


class audiobookbay:
    url: str = "https://audiobookbay.org/"
    urls: ClassVar[list[str]] = [
        "https://audiobookbay.org/",
        "http://theaudiobookbay.se/",
        "http://audiobookbay.fi/",
        "http://audiobookbay.is/",
    ]

    name: str = "AudioBook Bay (ABB)"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    class TorrentInfoParser(HTMLParser):
        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.url: str = url
            self.foundArchiveTitle: bool = False
            self.parseArchiveTitle: bool = False
            self.foundResult: bool = False
            self.foundTitle: bool = False
            self.parseTitle: bool = False
            self.torrentReady: bool = False
            self.totalPages: int = 0
            self.torrent_info: SearchResults = self.empty_torrent_info()

        def empty_torrent_info(self) -> SearchResults:
            return {
                "link": "",
                "name": "",
                "size": "100 MB",
                "seeds": 1,
                "leech": 1,
                "engine_url": self.url,
                "desc_link": "",
            }

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)

            if "archiveTitle" in (params.get("class") or ""):
                self.foundArchiveTitle = True

            if self.foundArchiveTitle and tag == "h3":
                self.parseArchiveTitle = True

            if "post" in (params.get("class") or ""):
                self.foundResult = True

            if self.foundResult and "postTitle" in (params.get("class") or ""):
                self.foundTitle = True

            if self.foundTitle and tag == "a":
                href = params.get("href")
                if href is None:
                    return
                self.torrent_info["desc_link"] = self.url + href
                self.parseTitle = True

            if tag == "a" and "»»" in (params.get("title") or ""):
                self.totalPages = int((params.get("href") or "").split("/")[2])

        @override
        def handle_endtag(self, tag: str) -> None:
            if self.torrentReady:
                desc_link = self.torrent_info.get("desc_link")
                if desc_link is None:
                    self.torrentReady = False
                    return
                size, magnet = self.fetchTorrentDetails(self.torrent_info["name"], desc_link)
                self.torrent_info["link"] = magnet
                if bool(size):
                    self.torrent_info["size"] = size

                _qbt_prettyPrinter(self.torrent_info)
                self.torrent_info = self.empty_torrent_info()
                self.foundResult = False
                self.torrentReady = False

        @override
        def handle_data(self, data: str) -> None:

            if self.parseTitle:
                if bool(data.strip()) and data != "\n":
                    self.torrent_info["name"] = data
                self.parseTitle = False
                self.foundTitle = False
                self.torrentReady = True

            if self.parseArchiveTitle:
                self.parseArchiveTitle = False
                self.foundArchiveTitle = False
                if data == "Not Found":
                    raise NotFoundError("Not Found")

        class TorrentPageParser(HTMLParser):
            def __init__(self):
                HTMLParser.__init__(self)
                self.hash: str = ""
                self.size: str = ""
                self.parseFileSize: bool = False
                self.parseHash: bool = False

            @override
            def handle_data(self, data: str):
                if data.strip() == "Info Hash:":
                    self.parseHash = True
                    return

                if (self.parseHash) and (bool(data.strip())):
                    self.hash = data.strip()
                    self.parseHash = False
                    return

                if data.strip() == "Combined File Size:":
                    self.parseFileSize = True
                    return

                if (self.parseFileSize) and (bool(data.strip())):
                    if bool(self.size):
                        self.size = self.size + data.replace("s", "")
                        self.parseFileSize = False
                        return
                    self.size = data

        def fetchTorrentDetails(self, title: str, url: str) -> tuple[str, str]:
            html = retrieve_url(url)
            parser = self.TorrentPageParser()
            parser.feed(html)

            link = (
                "magnet:"
                + "?xt=urn:btih:"
                + parser.hash
                + "&dn="
                + urllib.parse.quote(title)
                + "&tr=udp%3A%2F%2Ftracker.coppersurfer.tk%3A6969"
                + "&tr=udp%3A%2F%2Ftracker.leechers-paradise.org%3A6969"
                + "&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce"
                + "&tr=udp%3A%2F%2Ftracker.open-internet.nl%3A6969%2Fannounce"
                + "&tr=udp%3A%2F%2Ftracker.opentrackr.org%3A69691337%2Fannounce"
                + "&tr=udp%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce"
                + "&tr=http%3A%2F%2Ftracker.baravik.org%3A6970%2Fannounce"
                + "&tr=http%3A%2F%2Fretracker.telecom.by%3A80%2Fannounce"
                + "&tr=http%3A%2F%2Ftracker.vanitycore.co%3A6969%2Fannounce"
            )

            parser.close()

            return parser.size, link

    def find_healthy_url(self) -> str | None:
        """Checks multiple URLs in sequence and returns the first one that works."""
        for url in self.urls:
            response = retrieve_url(url)
            if response:
                return url

        return None

    def request(self, url: str, searchTerm: str, category: str, page: int = 1) -> str:
        request_url = url + "/page/" + str(page) + "/?s=" + searchTerm + "&cat=" + category
        return retrieve_url(request_url)

    def search(self, what: str, cat: str = "all") -> str | None:
        category = self.supported_categories[cat]

        url = self.find_healthy_url()

        if not url:
            print("No healthy url found!")
            return ""

        parser = self.TorrentInfoParser(url)

        try:
            parser.feed(self.request(url, what, category, 1))
            totalPages = parser.totalPages
            for page in range(2, min(totalPages, MAX_PAGES) + 1):
                parser.feed(self.request(url, what, category, page))
        finally:
            parser.close()
