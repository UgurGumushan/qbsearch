# VERSION: 1.3
"""
Pirateiro search. Reads bounded, deduplicated desktop HTML result rows.
The listing carries no size; each result links to a detail page whose magnet
is resolved by download_torrent, following a bounded download-button chain.
"""

from __future__ import annotations

import re
import urllib.parse
from html.parser import HTMLParser as _HTMLParser
from typing import TYPE_CHECKING, ClassVar

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
    from typing import final as _qbt_final
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
            done, pending = _qbt_wait(pending, timeout=remaining, return_when=_qbt_FIRST_COMPLETED)
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
    "_qbt_read_response",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


# Raised when a torrent page is missing its download link.
class ParseError(Exception):
    pass


class pirateiro:
    url: str = "https://pirateiro.io/"
    name: str = "Pirateiro"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "anime": "2",
        "games": "3",
        "movies": "1",
        "music": "4",
        "software": "6",
        "tv": "5",
    }
    max_pages: int = 10

    class HTMLParser(_HTMLParser):
        """Read desktop result rows without crossing into navigation or mobile cards."""

        def __init__(self, url: str):
            super().__init__(convert_charrefs=True)
            self.url: str = url
            self.noTorrents: bool = False
            self.seen_links: set[str] = set()
            self.emitted: int = 0
            self.in_row: bool = False
            self.row_link: str = ""
            self.title: list[str] = []
            self.in_title: bool = False
            self.peer: str = ""
            self.peer_text: list[str] = []
            self.seeds: int = -1
            self.leech: int = -1
            self.page_rows: int = 0

        @override
        def feed(self, data: str):
            self.page_rows = 0
            super().feed(data)
            self.noTorrents = self.page_rows == 0

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            params = dict(attrs)
            classes = (params.get("class") or "").split()
            if tag == "tr":
                self.in_row = True
                self.row_link = ""
                self.title = []
                self.in_title = False
                self.peer = ""
                self.seeds = self.leech = -1
            elif self.in_row and tag == "a":
                link = urllib.parse.urljoin(self.url, params.get("href") or "")
                parsed = urllib.parse.urlparse(link)
                if parsed.netloc == urllib.parse.urlparse(self.url).netloc and re.fullmatch(
                    r"/torrent/\d+", parsed.path
                ):
                    self.row_link = link
            elif self.in_row and tag == "h6" and "pt-title" in classes:
                self.in_title = True
            elif self.in_row and tag == "span":
                if "btn-seed-home" in classes:
                    self.peer = "seeds"
                elif "btn-leech-home" in classes:
                    self.peer = "leech"
                self.peer_text = []

        @override
        def handle_data(self, data: str):
            if self.in_title:
                self.title.append(data)
            if self.peer:
                self.peer_text.append(data)

        @override
        def handle_endtag(self, tag: str):
            if tag == "h6":
                self.in_title = False
            elif tag == "span" and self.peer:
                text = "".join(self.peer_text).strip()
                value = int(text) if text.isdecimal() else -1
                if self.peer == "seeds":
                    self.seeds = value
                else:
                    self.leech = value
                self.peer = ""
            elif tag == "tr" and self.in_row:
                self.in_row = False
                name = " ".join("".join(self.title).split())
                if not self.row_link or not name:
                    return
                self.page_rows += 1
                if self.row_link in self.seen_links or self.emitted >= MAX_DETAILS:
                    return
                self.seen_links.add(self.row_link)
                self.emitted += 1
                _qbt_prettyPrinter(
                    SearchResults(
                        link=self.row_link,
                        name=name,
                        size=-1,
                        seeds=self.seeds,
                        leech=self.leech,
                        engine_url=self.url,
                        desc_link=self.row_link,
                    )
                )

    class DownloadParser(_HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.magnet: str = ""
            self.next_link: str = ""

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            params = dict(attrs)
            href = params.get("href") or ""
            if tag != "a":
                return
            if href.startswith("magnet:"):
                values = urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("xt", [])
                if any(
                    re.fullmatch(r"urn:btih:(?:[a-fA-F0-9]{40}|[a-zA-Z2-7]{32})", v) for v in values
                ):
                    self.magnet = href
            elif "btn-down" in (params.get("class") or "").split():
                self.next_link = href

    def download_torrent(self, info: str, depth: int = 0) -> None:
        if depth >= MAX_DETAILS:
            raise ParseError("Too many detail redirects")
        if depth == 0:
            _ = _qbt_new_deadline()
        page_url = urllib.parse.unquote(info)
        parser = self.DownloadParser()
        parser.feed(retrieve_url(page_url))
        if parser.magnet:
            print(f"{parser.magnet} {info}")
            return
        if parser.next_link:
            link = urllib.parse.urljoin(page_url, parser.next_link)
            parsed = urllib.parse.urlparse(link)
            if parsed.scheme in ("http", "https"):
                self.download_torrent(link.replace("kickasstorrents", "katcr"), depth + 1)
                return
        raise ParseError("Torrent page has no usable magnet or download button")

    def search(self, what: str, cat: str = "all"):
        _ = _qbt_new_deadline()
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        cat_str = "" if cat == "all" else f"&category={self.supported_categories[cat]}"
        page_limit = min(max(0, self.max_pages), MAX_PAGES)
        for currPage in range(1, page_limit + 1):
            url = f"{self.url}search?query={what}&page={currPage}{cat_str}"
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.noTorrents or parser.emitted >= MAX_DETAILS:
                break
