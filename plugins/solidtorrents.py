# VERSION: 1.0
"""
Solid Torrents (https://solidtorrents.to) search engine. Scrapes search pages
with a bounded HTML parser supporting the redirected search layout and legacy
result cards. Pagination uses 20 results per page.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# Slim stdlib-only helpers for standalone engines (rendered by `bun run gen`).
try:
    import os as _qbt_os
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from collections.abc import Iterator as _QBTIterator
    from concurrent.futures import FIRST_COMPLETED as _qbt_FIRST_COMPLETED
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import wait as _qbt_wait
    from threading import Lock as _qbt_Lock
    from threading import local as _qbt_local
    from types import TracebackType as _QBTTracebackType
    from typing import TYPE_CHECKING
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
    from typing import final as _qbt_final
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error


def _qbt_default_workers() -> int:
    """Use available CPU cores for I/O overlap, with a hard per-engine ceiling."""
    default = min(16, max(4, _qbt_os.cpu_count() or 1))
    value = _qbt_os.environ.get("QBSEARCH_MAX_WORKERS")
    if value is None:
        return default
    try:
        return min(16, max(1, int(value)))
    except ValueError:
        return default


if TYPE_CHECKING:
    from typing_extensions import override
else:

    def override(function: _QBTCallable[..., object]) -> _QBTCallable[..., object]:
        return function


HTTP_TIMEOUT = 20.0
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.25
MAX_WORKERS = _qbt_default_workers()
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
    ) -> bool | None: ...


_qbt_urlopen_typed = _qbt_cast(_QBTCallable[..., _QBTResponseContext], _qbt_urlopen)
_qbt_int = _qbt_cast(_QBTCallable[[object], int], int)


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
        return max(0, _qbt_int(value))
    except (TypeError, ValueError):
        return max(0, int(MAX_RESPONSE_BYTES))


def _qbt_read_response(response: _QBTResponse, limit: object = None) -> bytes:
    """Read at most the configured response limit from an HTTP response."""
    return response.read(_qbt_response_limit(limit))


@_qbt_final
class _QBTBoundedResponse:
    """Response proxy that bounds the existing no-argument read() call sites."""

    def __init__(self, response: _QBTResponseContext) -> None:
        self._qbt_context: _QBTResponseContext = response
        self._qbt_response: _QBTResponse = response

    def __enter__(self) -> _QBTBoundedResponse:
        self._qbt_response = self._qbt_context.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: _QBTTracebackType | None,
    ) -> bool | None:
        return self._qbt_context.__exit__(exc_type, exc_value, traceback)

    def read(self, size: object = None, *_args: object, **_kwargs: object) -> bytes:
        if size is None:
            return _qbt_read_response(self._qbt_response)
        try:
            requested = _qbt_int(size)
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
        return _qbt_cast(object, getattr(self._qbt_response, name))


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


class _QBTWorkerState(_qbt_local):
    active: bool = False


_qbt_worker_state = _QBTWorkerState()
_QBT_FAILED_JOB = object()


def _qbt_call_job(worker: _QBTCallable[..., _QBTJobResult], job: object) -> _QBTJobResult:
    previous = _qbt_worker_state.active
    _qbt_worker_state.active = True
    try:
        if isinstance(job, tuple):
            return worker(*job)
        return worker(job)
    finally:
        _qbt_worker_state.active = previous


def _qbt_iter_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
    *,
    ordered: bool = False,
) -> _QBTIterator[_QBTJobResult]:
    """Stream completed jobs with bounded threads, buffering, and input consumption."""
    if deadline is None:
        deadline = _qbt_get_deadline()
    if deadline <= _qbt_time.monotonic():
        return
    # A worker may resolve a page's details, but must not create another pool.
    if _qbt_worker_state.active:
        for job in jobs:
            if deadline <= _qbt_time.monotonic():
                break
            try:
                nested_result = _qbt_call_job(worker, job)
            except Exception:
                continue
            yield nested_result
        return

    worker_limit = min(16, max(1, int(MAX_WORKERS)))
    job_iterator = iter(jobs)
    initial_jobs: list[object] = []
    for _ in range(worker_limit):
        try:
            initial_jobs.append(next(job_iterator))
        except StopIteration:
            break
    if not initial_jobs or deadline <= _qbt_time.monotonic():
        return

    executor = _QBTThreadPoolExecutor(max_workers=len(initial_jobs))
    pending: dict[_QBTFuture[_QBTJobResult], int] = {}
    completed: dict[int, object] = {}
    next_job = 0
    next_result = 0

    def submit(job: object) -> None:
        nonlocal next_job
        pending[executor.submit(_qbt_call_job, worker, job)] = next_job
        next_job += 1

    try:
        for job in initial_jobs:
            if deadline <= _qbt_time.monotonic():
                break
            submit(job)
        while pending:
            remaining = deadline - _qbt_time.monotonic()
            if remaining <= 0:
                break
            done, _ = _qbt_wait(pending, timeout=remaining, return_when=_qbt_FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                position = pending.pop(future)
                try:
                    result: object = future.result()
                except Exception:
                    result = _QBT_FAILED_JOB
                if ordered:
                    completed[position] = result
                elif result is not _QBT_FAILED_JOB:
                    yield _qbt_cast(_QBTJobResult, result)
            if ordered:
                while next_result in completed:
                    result = completed.pop(next_result)
                    next_result += 1
                    if result is not _QBT_FAILED_JOB:
                        yield _qbt_cast(_QBTJobResult, result)
            # Completed ordered results also occupy the window. A slow first job
            # cannot cause the entire input or response bodies to accumulate.
            while len(pending) + len(completed) < worker_limit:
                if deadline <= _qbt_time.monotonic():
                    break
                try:
                    job = next(job_iterator)
                except StopIteration:
                    break
                submit(job)
        # Preserve completed work if an earlier ordered job exceeded the deadline.
        for position in sorted(completed):
            result = completed[position]
            if result is not _QBT_FAILED_JOB:
                yield _qbt_cast(_QBTJobResult, result)
    finally:
        for future in pending:
            _ = future.cancel()
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            _ = executor.shutdown(wait=False)


def _qbt_run_parallel(
    worker: _QBTCallable[..., _QBTJobResult],
    jobs: _QBTIterable[object],
    deadline: float | None = None,
) -> list[_QBTJobResult]:
    """Eager compatibility adapter for engines whose workers emit their own results."""
    return list(_qbt_iter_parallel(worker, jobs, deadline))


__all__ = [
    "_qbt_iter_parallel",
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_read_response",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


SOLIDTORRENTS_RESULTS_RE = re.compile(
    r"Found\s+<span\b[^>]*>(\d+)</span>|<b>(\d+)</b>", re.IGNORECASE
)


def _stats_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return -1


class solidtorrents:
    url: str = "https://solidtorrents.to"
    name: str = "Solid Torrents"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all"}
    results_regex: str = SOLIDTORRENTS_RESULTS_RE.pattern

    class MyHtmlParser(HTMLParser):
        """Keep fields scoped to one card, including nested metadata elements."""

        VOID_TAGS: ClassVar[frozenset[str]] = frozenset(
            {
                "area",
                "base",
                "br",
                "col",
                "embed",
                "hr",
                "img",
                "input",
                "link",
                "meta",
                "param",
                "source",
                "track",
                "wbr",
            }
        )

        def __init__(self, url: str) -> None:
            super().__init__()
            self.url: str = url
            self.row: dict[str, str] = {}
            self.seen_links: set[str] = set()
            self._tags: list[str] = []
            self._main_depth: int = 0
            self._list_depth: int = 0
            self._card_depth: int = 0
            self._heading_depth: int = 0
            self._group_depth: int = 0
            self._group_index: int = 0
            self._column: int = 0
            self._field_depth: int = 0
            self._field_key: str = ""
            self._field_text: list[str] = []
            self._legacy: bool = False

        def _begin_field(self, key: str, depth: int) -> None:
            if key and not self._field_depth:
                self._field_key = key
                self._field_depth = depth
                self._field_text = []

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            if tag in self.VOID_TAGS:
                return
            self._tags.append(tag)
            depth = len(self._tags)
            params = dict(attrs)
            classes = set((params.get("class") or "").split())

            if not self._card_depth:
                if tag == "main" and "mx-auto" in classes:
                    self._main_depth = depth
                elif self._main_depth and tag == "div" and "space-y-4" in classes:
                    self._list_depth = depth
                elif (tag == "li" and "search-result" in classes) or (
                    self._list_depth and tag == "div" and "bg-white" in classes
                ):
                    self._card_depth = depth
                    self._legacy = tag == "li"
                    self.row = {}
                    self._heading_depth = 0
                    self._group_depth = 0
                    self._group_index = 0
                    self._column = 0
                    self._field_depth = 0
                    self._field_key = ""
                    self._field_text = []
                return

            if tag == "a":
                href = params.get("href") or ""
                if href.startswith("magnet:?"):
                    _ = self.row.setdefault("link", href)
                elif (self._legacy and self._heading_depth) or (
                    not self._legacy and self._group_index == 1 and self._group_depth
                ):
                    self.row["desc_link"] = urljoin(self.url, href)
                    self._begin_field("name", depth)
                return

            if self._legacy:
                if tag == "h5":
                    self._heading_depth = depth
                elif tag == "div" and "stats" in classes:
                    self._group_depth = depth
                    self._column = 0
                elif tag == "div" and self._group_depth and depth == self._group_depth + 1:
                    self._column += 1
                    key = {2: "size", 3: "seeds", 4: "leech", 5: "date"}.get(self._column, "")
                    self._begin_field(key, depth)
                return

            if tag == "div" and "items-center" in classes and not self._group_depth:
                self._group_depth = depth
                self._group_index += 1
                self._column = 0
            elif tag == "span" and self._group_depth:
                if self._group_index == 2 and depth == self._group_depth + 1:
                    self._column += 1
                    self._begin_field({2: "size", 3: "date"}.get(self._column, ""), depth)
                elif self._group_index == 3 and "font-medium" in classes:
                    self._column += 1
                    self._begin_field({1: "seeds", 2: "leech"}.get(self._column, ""), depth)

        @override
        def handle_data(self, data: str) -> None:
            if self._field_depth:
                self._field_text.append(data)

        @override
        def handle_endtag(self, tag: str) -> None:
            try:
                index = len(self._tags) - 1 - self._tags[::-1].index(tag)
            except ValueError:
                return
            depth = index + 1
            if self._field_depth and depth <= self._field_depth:
                value = "".join(self._field_text).strip()
                if value:
                    self.row[self._field_key] = value
                self._field_depth = 0
                self._field_text = []
            if self._heading_depth and depth <= self._heading_depth:
                self._heading_depth = 0
            if self._group_depth and depth <= self._group_depth:
                self._group_depth = 0
            if self._card_depth and depth <= self._card_depth:
                self._emit_result()
                self._card_depth = 0
            if self._list_depth and depth <= self._list_depth:
                self._list_depth = 0
            if self._main_depth and depth <= self._main_depth:
                self._main_depth = 0
            del self._tags[index:]

        def _emit_result(self) -> None:
            link = self.row.get("link", "")
            name = " ".join(self.row.get("name", "").split())
            if (
                not link
                or not name
                or link in self.seen_links
                or len(self.seen_links) >= MAX_DETAILS
            ):
                return
            result = SearchResults(
                link=link,
                name=name,
                size=self.row.get("size", "-1").replace(" ", ""),
                seeds=_stats_int(self.row.get("seeds", "-1")),
                leech=_stats_int(self.row.get("leech", "-1")),
                engine_url=self.url,
            )
            if self.row.get("desc_link"):
                result["desc_link"] = self.row["desc_link"]
            date = self.row.get("date")
            if date:
                try:
                    format_string = "%b %d, %Y" if self._legacy else "%m/%d/%Y"
                    parsed = datetime.strptime(date, format_string).replace(tzinfo=timezone.utc)
                    result["pub_date"] = int(parsed.timestamp())
                except ValueError:
                    pass
            self.seen_links.add(link)
            _qbt_prettyPrinter(result)

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def search(self, what: str, _cat: str = "all") -> None:
        _ = _qbt_new_deadline()
        parser = self.MyHtmlParser(self.url)
        query = what.replace("%20", "+").replace(" ", "+")
        first = retrieve_url(f"{self.url}/search?q={query}&page=1")
        match = SOLIDTORRENTS_RESULTS_RE.search(first)
        if match is not None:
            count = int(match.group(1) or match.group(2))
            pages = min(math.ceil(count / 20), MAX_PAGES)
            if pages > 0:
                parser.feed(first)
                for page in range(2, min(pages, MAX_PAGES) + 1):
                    if len(parser.seen_links) >= MAX_DETAILS:
                        break
                    html = retrieve_url(f"{self.url}/search?q={query}&page={page}")
                    if not html:
                        break
                    parser.feed(html)
        parser.close()
