# VERSION: 1.3
"""
XXXClub (https://xxxclub.to) search engine. Scrapes the browse-table rows;
for each row it fetches the detail page to extract the magnet link and the
size, and pages are walked concurrently in threads.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar, cast

from helpers import download_file
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


class xxxclubto:
    url: str = "https://xxxclub.to"
    headers: ClassVar[dict[str, str]] = {"Referer": url}
    name: str = "XXXClub"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "All",
        "pictures": "5",
    }

    container_regex: str = r'<div.*?class=".*?browsetableinside.*?".*?>(?s:.)*?<\/div>'
    pagination_regex: str = r'<div.*?class=".*?browsepagination.*?".*?>(?s:.)*?<\/div>'
    pagination_next_regex: str = r'<a.*?title="Next Page".*?>(?s:.)*?<\/a>'
    pagination_last_page: str = r'<a.*?class=".*?active.*?".*?>.*?</a>'
    items_regex: str = r"<li.*?>(?s:.)*?<\/li>"

    has_results: bool = True
    has_next_page: bool = True
    last_page: int = 100

    class MyHtmlParser(HTMLParser):
        def error(self, _message: str):
            pass

        UL: str = "ul"
        LI: str = "li"
        SPAN: str = "span"
        A: str = "a"

        def __init__(self, url: str, headers: dict[str, str]) -> None:
            HTMLParser.__init__(self)
            self.url: str = url
            self.headers: dict[str, str] = headers
            self.headers["Referer"] = url
            self.row: dict[str, str] = {}
            self.column: int = 0
            self.foundResults: bool = False
            self.foundTable: bool = False
            self.insideRow: bool = False
            self.insideCell: bool = False
            self.insideNameLink: bool = False
            self.foundTableHeading: bool = False
            self.foundRowCatlabe: bool = False
            self.magnet_regex: str = r'href="magnet:.*"'

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            params = dict(attrs)
            if "browsetableinside" in (params.get("class") or ""):
                self.foundResults = True
                return
            if self.foundResults and tag == self.UL:
                self.foundTable = True
                return
            if self.foundTable and tag == self.LI:
                self.insideRow = True
                return
            if self.insideRow and self.foundTableHeading and tag == self.SPAN:
                classList = params.get("class", None)
                if self.foundRowCatlabe:
                    self.insideCell = True
                    self.column += 1
                if "catlabe" == classList:
                    self.foundRowCatlabe = True
                return
            if self.insideRow and self.foundTableHeading and self.column == 1 and tag == self.A:
                href = params.get("href")
                if not href:
                    return
                self.insideNameLink = True
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                self.row["link"] = link
                torrent_page = retrieve_url(link, self.headers)
                matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                magnet_urls = [x.group() for x in matches]
                self.row["link"] = magnet_urls[0].split('"')[1]
                return

        @override
        def handle_data(self, data: str):
            if self.insideCell and self.foundRowCatlabe:
                if self.column == 1 and self.insideNameLink:
                    self.row["name"] = data
                if self.column == 3:
                    size = data.replace(",", "")
                    self.row["size"] = size
                if self.column == 4:
                    self.row["seeds"] = data
                if self.column == 5:
                    self.row["leech"] = data

        @override
        def handle_endtag(self, tag: str):
            if self.insideCell and self.insideNameLink and tag == self.A:
                self.insideNameLink = False
            if self.insideCell and tag == self.SPAN:
                self.insideCell = False
            if self.insideRow and tag == self.LI:
                if not self.foundTableHeading:
                    self.foundTableHeading = True
                else:
                    self.row["engine_url"] = self.url
                    _qbt_prettyPrinter(cast(SearchResults, cast(object, self.row)))
                    self.insideRow = False
                    self.foundRowCatlabe = False
                    self.column = 0
                    self.row = {}
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def get_page_url(self, what: str, category: str, page: int) -> str:
        return f"{self.url}/torrents/search/{category}/{what}?page={page}&sort=seeders&order=asc"

    def get_results(self, html: str) -> None:
        container_matches = re.finditer(self.container_regex, html, re.MULTILINE)
        container = [x.group() for x in container_matches]

        if len(container) > 0:
            container_html = container[0]
            items_matches = re.finditer(self.items_regex, container_html, re.MULTILINE)
            items = [x.group() for x in items_matches]
            self.has_results = len(items) > 1
        else:
            self.has_results = False

    def get_next_page(self, html: str) -> None:
        next_page_matches = re.finditer(self.pagination_next_regex, html, re.MULTILINE)
        next_page = [x.group() for x in next_page_matches]

        if len(next_page) == 0:
            self.has_next_page = False
            self.get_last_page(html)

    def get_last_page(self, html: str) -> None:
        last_page_matches = re.finditer(self.pagination_last_page, html, re.MULTILINE)
        last_page = [x.group() for x in last_page_matches]

        if len(last_page) == 0:
            self.last_page = 1
        else:
            self.last_page = int(re.sub(r"</a>", "", re.sub(r"<a.*?>", "", last_page[0])))

    def threaded_search(self, page: int, what: str, cat: str) -> bool:
        page_url = self.get_page_url(what, cat, page)
        headers = dict(self.headers)
        headers["Referer"] = page_url
        retrieved_html = retrieve_url(page_url, headers)
        if not retrieved_html:
            return False
        container_matches = re.finditer(self.container_regex, retrieved_html, re.MULTILINE)
        container = [x.group() for x in container_matches]
        has_results = False
        if container:
            items_matches = re.finditer(self.items_regex, container[0], re.MULTILINE)
            has_results = len([x.group() for x in items_matches]) > 1
        next_page_matches = re.finditer(self.pagination_next_regex, retrieved_html, re.MULTILINE)
        has_next_page = bool([x.group() for x in next_page_matches])
        parser = self.MyHtmlParser(self.url, headers)
        if has_results:
            parser.feed(retrieved_html)
            parser.close()
        return bool(has_results and has_next_page)

    def search(self, what: str, cat: str = "all") -> None:
        category = self.supported_categories[cat]
        batch_size = max(1, int(MAX_WORKERS))
        for start in range(1, MAX_PAGES + 1, batch_size):
            pages = range(start, min(start + batch_size, MAX_PAGES + 1))
            jobs = [(p, what, category) for p in pages]
            outcomes = _qbt_run_parallel(self.threaded_search, jobs, _qbt_new_deadline())
            if len(outcomes) != len(jobs) or not all(outcomes):
                break
