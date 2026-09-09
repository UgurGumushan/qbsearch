# VERSION: 1.03
"""
Sukebei Nyaa adult anime search. Scrapes the HTML results table and follows
the pagination, reading the total count from the "Displaying results 1-N out
of M results" footer line.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import ClassVar

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


# some other imports if necessary
class nyaa_phuong:
    url: str = "https://sukebei.nyaa.si"
    name: str = "Sukebei Nyaa"  # spaces and special characters are allowed here
    # Which search categories are supported by this search engine and their corresponding id
    # Possible categories are ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "6",
        "tv": "4",
        "music": "1",
        "games": "2",
        "anime": "7",
        "software": "3",
    }

    def __init__(self) -> None:
        pass

    class RowParser(HTMLParser):
        """Collects the <tr> rows of the results table.

        Each row is a list of cells; each cell is (text, [hrefs]) so the
        anchor hrefs inside a <td> are preserved (the original bs4 code read
        a.get('href'), not the cell text)."""

        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.rows: list[list[tuple[str, list[str]]]] = []
            self.in_results: bool = False
            self.depth: int = 0
            self.cur: list[tuple[str, list[str]]] | None = None
            self.cell: tuple[str, list[str]] | None = None

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = dict(attrs)
            if tag == "table":
                self.depth += 1
                if not self.in_results and "results" in (params.get("class") or ""):
                    self.in_results = True
                return
            if not self.in_results:
                return
            if tag == "tr":
                self.cur = []
            elif tag == "td" and self.cur is not None:
                self.cell = ("", [])
            elif tag == "a" and self.cell is not None:
                href = params.get("href")
                if href is not None:
                    self.cell[1].append(href)

        @override
        def handle_data(self, data: str) -> None:
            if self.cell is not None:
                self.cell = (self.cell[0] + data, self.cell[1])

        @override
        def handle_endtag(self, tag: str) -> None:
            if not self.in_results:
                return
            if tag == "td" and self.cell is not None and self.cur is not None:
                self.cur.append(self.cell)
                self.cell = None
            elif tag == "tr" and self.cur is not None:
                self.rows.append(self.cur)
                self.cur = None
            elif tag == "table":
                self.depth -= 1
                if self.depth <= 0:
                    self.in_results = False

    @staticmethod
    def _cell_text(cell: tuple[str, list[str]]) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cell[0])).strip()

    @staticmethod
    def _first_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][0] if cell[1] else ""

    @staticmethod
    def _last_href(cell: tuple[str, list[str]]) -> str:
        return cell[1][-1] if cell[1] else ""

    @staticmethod
    def _size_bytes(raw: str) -> int:
        m = re.search(r"([\d.]+)\s*([A-Za-z]+)", raw)
        if not m:
            return 0
        value = float(m.group(1))
        unit = m.group(2)
        if unit == "GiB":
            return int(value * 1073741824)
        if unit == "MiB":
            return int(value * 1000000)
        return 0

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, _cat: str = "all") -> None:
        # what is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        # cat is the name of a search category in ('all', 'movies', 'tv', 'music', 'games', 'anime', 'software', 'pictures', 'books')
        # q - query, f - filter, c - category
        _qbt_new_deadline()
        base_url = "https://sukebei.nyaa.si/?q=%s&f=0&c=0_0"
        base_url_with_query = base_url % what
        response = retrieve_url(base_url_with_query)
        info = re.search(r"Displaying results 1-(\d+) out of (\d+) results", response)
        if info is None:
            return
        item_per_pages = int(info.group(1))
        total_results = int(info.group(2))
        number_of_page = (
            math.ceil(total_results / item_per_pages) if item_per_pages != 0 else 1
        )
        seen_results: set[str] = set()
        emitted = 0
        for page in range(1, min(int(number_of_page), MAX_PAGES) + 1):
            if page > 1:
                response = retrieve_url(base_url_with_query + f"&p={page!s}")
            parser = self.RowParser()
            parser.feed(response)
            parser.close()
            for tds in parser.rows:
                if emitted >= MAX_DETAILS:
                    break
                if len(tds) < 7:
                    continue
                ref = self._first_href(tds[1])
                title = self._cell_text(tds[1])
                link = self._last_href(tds[2])
                result_key = link or ref
                if not result_key or result_key in seen_results:
                    continue
                seen_results.add(result_key)
                sizeInBytes = self._size_bytes(self._cell_text(tds[3]))
                seeders = self._cell_text(tds[5])
                leechers = self._cell_text(tds[6])
                try:
                    pub_date = int(
                        datetime.strptime(self._cell_text(tds[4]), "%Y-%m-%d %H:%M")
                        .replace(tzinfo=timezone.utc)
                        .timestamp()
                    )
                except ValueError:
                    pub_date = -1
                try:
                    seeds = int(seeders)
                except ValueError:
                    seeds = -1
                try:
                    leech = int(leechers)
                except ValueError:
                    leech = -1
                res: SearchResults = {
                    "link": link,
                    "name": title,
                    "size": str(sizeInBytes),
                    "seeds": seeds,
                    "leech": leech,
                    "engine_url": self.url,
                    "desc_link": self.url + ref,
                    "pub_date": pub_date,
                }
                _qbt_prettyPrinter(res)
                emitted += 1
            if emitted >= MAX_DETAILS:
                break
