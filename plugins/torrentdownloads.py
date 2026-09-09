# VERSION: 1.1
"""
Torrent Downloads (https://torrentdownloads.pro) search engine. Scrapes
result rows and, for each row, fetches the torrent page to extract the magnet
link (rows without a /torrent/ link, i.e. featured links, are skipped); later
pages are walked concurrently in threads.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# Slim stdlib-only helpers for standalone engines (rendered by `bun run gen`).
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import FIRST_COMPLETED as _qbt_FIRST_COMPLETED
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import wait as _qbt_wait
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
MAX_RESPONSE_BYTES = 4 * 1024 * 1024

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


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


def _qbt_new_deadline() -> float:
    global _qbt_search_deadline
    _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


def _qbt_sleep(attempt: int, deadline: float | None = None) -> bool:
    if deadline is None:
        deadline = _qbt_get_deadline()
    remaining = deadline - _qbt_time.monotonic()
    if remaining <= 0:
        return False
    delay = min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0, remaining)
    if delay > 0:
        _qbt_time.sleep(delay)
    return _qbt_time.monotonic() < deadline


class _QBTEmptyResponse:
    """Empty response fallback so one dead request never aborts a search."""

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


def _qbt_response_limit(limit: object = None) -> int:
    value = MAX_RESPONSE_BYTES if limit is None else limit
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(MAX_RESPONSE_BYTES))


def _qbt_read_response(response: _QBTResponse, limit: object = None) -> bytes:
    """Read at most the configured response limit from an HTTP response."""
    return response.read(_qbt_response_limit(limit))


class _QBTBoundedResponse:
    """Response proxy that bounds the existing no-argument read() call sites."""

    def __init__(self, response: _QBTResponse) -> None:
        self._qbt_response = response

    def __enter__(self) -> "_QBTBoundedResponse":
        self._qbt_response = self._qbt_response.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool:
        return self._qbt_response.__exit__(exc_type, exc_value, traceback)

    def read(self, size: object = None, *_args: object, **_kwargs: object) -> bytes:
        if size is None:
            return _qbt_read_response(self._qbt_response)
        try:
            requested = int(size)
        except (TypeError, ValueError):
            return _qbt_read_response(self._qbt_response)
        if requested < 0:
            return _qbt_read_response(self._qbt_response)
        return _qbt_read_response(
            self._qbt_response,
            min(requested, _qbt_response_limit()),
        )

    def close(self) -> None:
        self._qbt_response.close()

    def __getattr__(self, name: str) -> object:
        return getattr(self._qbt_response, name)


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times; return empty on failure."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
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
        if attempt + 1 < attempts and not _qbt_sleep(attempt):
            return ""
    return ""


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with timeout/retry policy; return an empty response when exhausted."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=timeout)
            else:
                response = _qbt_urlopen_typed(url, data=data, timeout=timeout, context=context)
            status: object = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return _qbt_cast(
                _QBTResponseContext,
                _qbt_cast(object, _QBTBoundedResponse(response)),
            )
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
            return _qbt_empty_response(url)
        if attempt + 1 < attempts and not _qbt_sleep(attempt):
            return _qbt_empty_response(url)
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
    if deadline is None:
        deadline = _qbt_get_deadline()
    if deadline - _qbt_time.monotonic() <= 0:
        return []
    worker_limit = max(1, int(MAX_WORKERS))
    job_iterator = iter(jobs)
    initial_jobs: list[object] = []
    for _ in range(worker_limit):
        try:
            initial_jobs.append(next(job_iterator))
        except StopIteration:
            break
    if not initial_jobs or deadline - _qbt_time.monotonic() <= 0:
        return []
    executor = _QBTThreadPoolExecutor(max_workers=len(initial_jobs))
    pending: set[_QBTFuture[_QBTJobResult]] = set()
    results: list[_QBTJobResult] = []
    try:
        for job in initial_jobs:
            if deadline - _qbt_time.monotonic() <= 0:
                break
            if isinstance(job, tuple):
                pending.add(executor.submit(worker, *job))
            else:
                pending.add(executor.submit(worker, job))
        while pending:
            remaining = deadline - _qbt_time.monotonic()
            if remaining <= 0:
                break
            done, pending = _qbt_wait(
                pending,
                timeout=remaining,
                return_when=_qbt_FIRST_COMPLETED
            )
            if not done:
                break
            for future in done:
                try:
                    results.append(future.result())
                except Exception:
                    pass
                if deadline - _qbt_time.monotonic() <= 0:
                    continue
                try:
                    job = next(job_iterator)
                except StopIteration:
                    continue
                if isinstance(job, tuple):
                    pending.add(executor.submit(worker, *job))
                else:
                    pending.add(executor.submit(worker, job))
    finally:
        for future in pending:
            _ = future.cancel()
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            _ = executor.shutdown(wait=False)
    return results


__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_read_response",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


class torrentdownloads:
    url: str = "https://torrentdownloads.pro"
    name: str = "Torrent Downloads"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "anime": "1",
        "books": "2",
        "games": "3",
        "movies": "4",
        "music": "5",
        "software": "7",
        "tv": "8",
    }

    next_page_regex: str = r"<a.*?>>><\/a>"
    has_next_page: bool = True

    class MyHtmlParser(HTMLParser):
        def error(self, _message: str):
            pass

        DIV: str = "div"
        P: str = "p"
        A: str = "a"
        SPAN: str = "span"
        B: str = "b"

        def __init__(
            self,
            url: str,
            seen_detail_links: set[str],
            seen_result_links: set[str],
            state_lock: object,
        ):
            HTMLParser.__init__(self)
            self.magnet_regex: str = r'href=["\'](magnet:[^"\']+)["\']'

            self.url: str = url
            self.seen_detail_links = seen_detail_links
            self.seen_result_links = seen_result_links
            self.state_lock = state_lock
            self.row: dict[str, str | int] = {}
            self.column: int = 0

            self.foundContainer: bool = False
            self.insideRow: bool = False
            self.insideCell: bool = False
            self.insideNameCell: bool = False

            self.shouldParseName: bool = False
            self.shouldGetCategory: bool = False
            self.shouldGetSize: bool = False
            self.shouldGetSeeds: bool = False
            self.shouldGetLeechs: bool = False

            self.alreadyParseName: bool = False
            self.alreadyParsesLink: bool = False
            self.shouldSkipResult: bool = False

        def _claim(self, values: set[str], value: str, limit=None) -> bool:
            if not value:
                return False
            with self.state_lock:
                if value in values or (limit is not None and len(values) >= limit):
                    return False
                values.add(value)
                return True

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            params = dict(attrs)
            cssClasses = params.get("class") or ""

            if "inner_container" in cssClasses:
                self.foundContainer = True

            if "grey_bar3" in cssClasses and tag == self.DIV:
                self.insideRow = True

            if self.insideRow and tag == self.SPAN and not self.shouldSkipResult:
                self.column += 1
                self.insideCell = True

            if self.insideRow and tag == self.P:
                self.insideNameCell = True

            if self.insideCell:
                if self.column == 2:
                    self.shouldGetLeechs = True

                if self.column == 3:
                    self.shouldGetSeeds = True

                if self.column == 4:
                    self.shouldGetSize = True

            if self.insideNameCell and tag == self.A:
                self.shouldParseName = True
                href = params.get("href") or ""
                if href.startswith("/torrent/"):
                    link = f"{self.url}/{href}"
                    self.row["desc_link"] = link

                    if not self._claim(self.seen_detail_links, link, MAX_DETAILS):
                        self.shouldSkipResult = True
                        return
                    torrent_page = retrieve_url(link)
                    magnet_match = re.search(self.magnet_regex, torrent_page, re.MULTILINE)
                    if magnet_match is None:
                        self.shouldSkipResult = True
                        return
                    self.row["link"] = magnet_match.group(1)
                else:
                    self.shouldSkipResult = True

            if self.insideNameCell and tag == self.B:
                self.shouldSkipResult = True

        @override
        def handle_data(self, data: str):
            if self.shouldParseName:
                self.row["name"] = data
                self.shouldParseName = False

            if self.shouldGetSize:
                size = data.replace("&nbsp;", "").replace("\xa0", " ")
                self.row["size"] = size
                self.shouldGetSize = False

            if self.shouldGetSeeds:
                self.row["seeds"] = data
                self.shouldGetSeeds = False

            if self.shouldGetLeechs:
                self.row["leech"] = data
                self.shouldGetLeechs = False

        @override
        def handle_endtag(self, tag: str):
            if tag == self.SPAN or tag == self.P:
                self.insideCell = False

            if tag == self.P:
                self.insideNameCell = False

            if tag == self.DIV and self.insideRow:
                self.row["engine_url"] = self.url
                result_link = str(self.row.get("link", ""))
                if not self.shouldSkipResult and self._claim(
                    self.seen_result_links, result_link
                ):
                    _qbt_prettyPrinter(
                        SearchResults(
                            link=str(self.row.get("link", "")),
                            name=str(self.row.get("name", "")),
                            size=str(self.row.get("size", "")),
                            seeds=int(str(self.row.get("seeds", 0)).strip() or 0),
                            leech=int(str(self.row.get("leech", 0)).strip() or 0),
                            engine_url=self.url,
                            desc_link=str(self.row.get("desc_link", "")),
                        )
                    )
                self.column = 0
                self.row = {}
                self.insideRow = False
                self.shouldSkipResult = False

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def getPageUrl(self, what: str, cat: str, page: int) -> str:
        return f"{self.url}/search/?new=1&s_cat={cat}&search={what}&page={page}"

    def threaded_search(self, page: int, what: str, cat: str) -> bool:
        parser = self.MyHtmlParser(
            self.url,
            self._seen_detail_links,
            self._seen_result_links,
            self._state_lock,
        )
        page_url = self.getPageUrl(what, cat, page)
        retrievedHtml = retrieve_url(page_url)
        if not retrievedHtml:
            return False
        parser.feed(retrievedHtml)
        parser.close()
        return re.search(self.next_page_regex, retrievedHtml, re.MULTILINE) is not None

    def search(self, what: str, cat: str = "all") -> None:
        search_category = self.supported_categories[cat]
        what = what.replace("%20", "+")
        what = what.replace(" ", "+")

        self._seen_detail_links: set[str] = set()
        self._seen_result_links: set[str] = set()
        self._state_lock = _qbt_Lock()
        self.has_next_page = True
        batch_size = max(1, int(MAX_WORKERS))
        for start in range(1, MAX_PAGES + 1, batch_size):
            pages = range(start, min(start + batch_size, MAX_PAGES + 1))
            jobs = [(p, what, search_category) for p in pages]
            outcomes = _qbt_run_parallel(self.threaded_search, jobs, _qbt_new_deadline())
            if len(outcomes) != len(jobs) or not all(outcomes):
                self.has_next_page = False
                break
