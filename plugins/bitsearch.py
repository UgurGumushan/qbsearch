# VERSION: 1.3
"""Bit Search engine: general torrent search on bitsearch.to.

Results are magnet links and every result page is fetched, up to ten
pages per search.
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime
from html.parser import HTMLParser
from typing import ClassVar

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


def stats_int(value: str | int) -> int:
    try:
        return int(value)
    except ValueError:
        return -1


class bitsearch:
    url: str = "https://bitsearch.to"
    name: str = "Bit Search"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}

    results_regex: str = r"Found\s+<span.+>\d+<\/span>"

    class MyHtmlParser(HTMLParser):
        def error(self, _message: str) -> None:
            pass

        MAIN: str = "main"
        DIV: str = "div"
        SPAN: str = "span"
        A: str = "a"

        search_results_main_class_name: str = "mx-auto"
        search_results_list_class_name: str = "space-y-4"
        search_results_item_container_class_name: str = "bg-white"
        search_results_item_class_name: str = "items-start"
        search_results_torrent_info_class_name: str = "flex-1"
        search_results_item_metadata_class_name: str = "items-center"
        search_results_item_metadata_numbers_class_name: str = "font-medium"
        search_results_item_download_class_name: str = "space-y-2"
        search_results_item_mobile_download_class_name: str = "sm:hidden"

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)

            self.url: str = url
            self.row: dict[str, str] = {}

            self.column: int = 0
            self.metadata: int = 0
            self.results: int = 0

            self.insideMain: bool = False
            self.insideSearchResultList: bool = False
            self.insideSearchResultItemContainer: bool = False
            self.insideSearchResultItem: bool = False
            self.insideTorrentInfo: bool = False
            self.insideName: bool = False
            self.insideStats: bool = False
            self.insideSwarm: bool = False
            self.insideDownload: bool = False
            self.insideMobileDownload: bool = False
            self.shouldGetName: bool = False
            self.shouldGetData: bool = False

            self.cssClasses: list[object] = []

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            cssClasses = params.get("class") or ""

            if tag == self.MAIN and self.search_results_main_class_name in cssClasses:
                self.insideMain = True
                return

            if (
                self.insideMain
                and tag == self.DIV
                and self.search_results_list_class_name in cssClasses
            ):
                self.insideSearchResultList = True
                return

            if (
                self.insideSearchResultList
                and tag == self.DIV
                and self.search_results_item_container_class_name in cssClasses
            ):
                self.insideSearchResultItemContainer = True
                return

            if (
                self.insideSearchResultItemContainer
                and tag == self.DIV
                and self.search_results_item_class_name in cssClasses
            ):
                self.insideSearchResultItem = True
                return

            if (
                self.insideSearchResultItem
                and tag == self.DIV
                and self.search_results_torrent_info_class_name in cssClasses
            ):
                self.insideTorrentInfo = True
                return

            if (
                self.insideSearchResultItem
                and tag == self.DIV
                and self.search_results_item_metadata_class_name in cssClasses
            ):
                if self.metadata == 0:
                    self.insideName = True
                    self.metadata = 1
                    return
                if self.metadata == 1:
                    # stats
                    self.insideName = False
                    self.insideStats = True
                    self.column = 0
                    self.metadata = 2
                    return
                if self.metadata == 2:
                    # swarm
                    self.insideStats = False
                    self.insideSwarm = True
                    self.column = 0
                    self.metadata = 3
                    return

            if self.insideName and tag == self.A:
                self.shouldGetName = True
                href = params.get("href") or ""
                link = f"{self.url}{href}"
                self.row["desc_link"] = link
                return

            if self.insideStats and tag == self.SPAN and len(cssClasses) == 0:
                self.column += 1
                self.shouldGetData = True
                return

            if (
                self.insideSwarm
                and tag == self.SPAN
                and self.search_results_item_metadata_numbers_class_name in cssClasses
            ):
                self.column += 1
                self.shouldGetData = True
                return

            if (
                self.insideSearchResultItem
                and tag == self.DIV
                and self.search_results_item_download_class_name in cssClasses
            ):
                self.insideDownload = True
                return

            if (
                self.insideSearchResultItemContainer
                and tag == self.DIV
                and self.search_results_item_mobile_download_class_name in cssClasses
            ):
                self.insideMobileDownload = True
                return

            if self.insideDownload and tag == self.A:
                href = params.get("href") or ""
                if href.startswith("magnet"):
                    self.row["link"] = href
                return

        @override
        def handle_data(self, data: str) -> None:
            if self.shouldGetName:
                self.row["name"] = data.strip()
                self.shouldGetName = False
                return

            if self.insideStats and self.shouldGetData:
                if self.column == 2:
                    self.row["size"] = data.replace(" ", "")
                    self.shouldGetData = False
                    return
                if self.column == 3:
                    self.row["pub_date"] = str(
                        int(datetime.strptime(data.strip(), "%m/%d/%Y").timestamp())
                    )
                    self.shouldGetData = False
                    return

            if self.insideSwarm and self.shouldGetData:
                if self.column == 1:
                    self.row["seeds"] = data
                    self.shouldGetData = False
                    return
                if self.column == 2:
                    self.row["leech"] = data
                    self.shouldGetData = False
                    return

        @override
        def handle_endtag(self, tag: str) -> None:
            if self.insideSwarm and tag == self.DIV:
                self.insideSwarm = False
                self.column = 0
                self.metadata = 0
                return

            if (
                self.insideTorrentInfo
                and tag == self.DIV
                and not self.insideName
                and not self.insideStats
                and not self.insideSwarm
            ):
                self.insideTorrentInfo = False
                return

            if self.insideDownload and tag == self.DIV:
                self.insideDownload = False
                return

            if self.insideMobileDownload and tag == self.DIV:
                self.insideMobileDownload = False
                return

            if (
                tag == self.DIV
                and not self.insideDownload
                and not self.insideTorrentInfo
                and not self.insideMobileDownload
                and self.insideSearchResultItem
            ):
                self.insideSearchResultItem = False
                return

            if (
                tag == self.DIV
                and not self.insideSearchResultItem
                and self.insideSearchResultItemContainer
            ):
                self.insideSearchResultItemContainer = False
                row = self.row
                res = SearchResults(
                    link=row["link"],
                    name=row["name"],
                    size=row["size"],
                    seeds=stats_int(row["seeds"]),
                    leech=stats_int(row["leech"]),
                    engine_url=self.url,
                )
                if "desc_link" in row:
                    res["desc_link"] = row["desc_link"]
                if "pub_date" in row:
                    res["pub_date"] = int(row["pub_date"])
                _qbt_prettyPrinter(res)
                self.column = 0
                self.metadata = 0
                return

            if tag == self.DIV and not self.insideSearchResultItem and self.insideSearchResultList:
                self.insideSearchResultList = False
                return

            if tag == self.MAIN and self.insideMain:
                self.insideMain = False
                return

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def search(self, what: str, _cat: str = "all"):
        parser = self.MyHtmlParser(self.url)
        what = what.replace("%20", "+")
        what = what.replace(" ", "+")
        page = 1

        page_url = f"{self.url}/search?q={what}&page={page}"
        retrievedHtml = retrieve_url(page_url)
        results_matches = re.finditer(self.results_regex, retrievedHtml, re.MULTILINE)
        results_array = [x.group() for x in results_matches]

        if len(results_array) > 0:
            m = re.search(r"\d+", results_array[0])
            results = int(m.group(0)) if m else 0
            pages = math.ceil(results / 20)
        else:
            pages = 0

        page += 1

        if pages > 0:
            parser.feed(retrievedHtml)

            while page <= min(pages, 10, MAX_PAGES):
                page_url = f"{self.url}/search?q={what}&page={page}"

                try:
                    retrievedHtml = retrieve_url(page_url)
                    parser.feed(retrievedHtml)
                except Exception:
                    pass
                page += 1
                time.sleep(0.75)
        parser.close()
