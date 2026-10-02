# VERSION: 1.0
# SPDX-License-Identifier: GPL-3.0-or-later
"""UIndex guest search: one table page with supplied magnets; no login or details."""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Callable, ClassVar, final
from urllib.parse import parse_qs, quote, unquote, urljoin, urlsplit
from urllib.request import Request

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

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


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return -1
    try:
        number = int(value)
        return number if 0 <= number <= 9223372036854775807 else -1
    except (ValueError, OverflowError):
        return -1


def _http(value: object) -> str:
    url = _text(value)
    if any(ord(char) <= 32 for char in url):
        return ""
    try:
        parsed = urlsplit(url)
        return (
            url
            if parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not (parsed.username or parsed.password)
            else ""
        )
    except ValueError:
        return ""


def _hash(value: object) -> str:
    value = _text(value)
    if re.fullmatch(r"[a-fA-F0-9]{40}", value):
        return value.lower()
    if re.fullmatch(r"[A-Z2-7a-z]{32}", value):
        try:
            return base64.b32decode(value.upper()).hex()
        except ValueError:
            pass
    return ""


def _magnet(value: object, info_hash: object, title: str) -> tuple[str, str]:
    digest = _hash(info_hash)
    magnet = _text(value)
    if magnet.lower().startswith("magnet:?") and not any(ord(c) < 32 for c in magnet):
        try:
            for item in parse_qs(urlsplit(magnet).query).get("xt", []):
                if item.lower().startswith("urn:btih:"):
                    found = _hash(item[9:])
                    if found and (not digest or found == digest):
                        return magnet, found
        except ValueError:
            pass
    if digest:
        return f"magnet:?xt=urn:btih:{digest}&dn={quote(title, safe='')}", digest
    return "", ""


def _date(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return _number(value)
    value = _text(value)
    if not value:
        return -1
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return int(moment.timestamp())
    except (ValueError, OverflowError):
        return -1


def _read(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": "qbsearch/0.1 (qBittorrent search plugin)",
            "Accept": "application/json,application/xml,text/html;q=0.9",
        },
    )
    try:
        with _qbt_safe_urlopen(request) as response:
            return response.read().decode("utf-8-sig")
    except (UnicodeError, ValueError, OSError):
        return ""


def _emit(
    site: str,
    seen: set[str],
    title: object,
    magnet: object,
    info_hash: object,
    size: object,
    seeds: object,
    leech: object,
    detail: object,
    date: object = None,
) -> bool:
    name = _text(title)
    if (
        not name
        or len(seen) >= min(100, MAX_DETAILS)
        or _qbt_time.monotonic() >= _qbt_get_deadline()
    ):
        return False
    link, key = _magnet(magnet, info_hash, name)
    if not link or key in seen:
        return False
    seen.add(key)
    _qbt_prettyPrinter(
        {
            "name": name,
            "link": link,
            "size": size
            if isinstance(size, str)
            and re.fullmatch(r"\d+(?:[.,]\d+)?\s*[KMGTPE]?i?B", size, re.IGNORECASE)
            else _number(size),
            "seeds": _number(seeds),
            "leech": _number(leech),
            "desc_link": _http(detail) or site,
            "engine_url": site,
            "pub_date": _date(date),
        }
    )
    return True


@final
class _Rows(HTMLParser):
    """Keep one table row, with bounded cell/anchor text instead of a DOM."""

    def __init__(self, consumer: Callable[[list[str], list[tuple[int, str, str]]], None]) -> None:
        super().__init__(convert_charrefs=True)
        self.consumer = consumer
        self.cells: list[str] = []
        self.links: list[tuple[int, str, str]] = []
        self.cell = -1
        self.href = ""
        self.title = ""
        self.anchor = ""
        self.in_row = False
        self.ignored = 0

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.ignored += 1
        if tag == "tr":
            self.cells, self.links = [], []
            self.cell = -1
            self.in_row = True
        elif self.in_row and tag in {"td", "th"}:
            self.cell += 1
            if len(self.cells) < 16:
                self.cells.append("")
        elif self.in_row and tag == "a":
            attributes = dict(attrs)
            self.href = attributes.get("href") or ""
            self.title = attributes.get("title") or ""
            self.anchor = ""

    @override
    def handle_data(self, data: str) -> None:
        if not self.in_row or self.ignored:
            return
        if 0 <= self.cell < len(self.cells):
            self.cells[self.cell] = (self.cells[self.cell] + data)[:4096]
        if self.href:
            self.anchor = (self.anchor + data)[:2048]

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self.ignored = max(0, self.ignored - 1)
        elif tag == "a" and self.href:
            if len(self.links) < 32:
                self.links.append((self.cell, self.href, self.title or self.anchor.strip()))
            self.href = ""
        elif tag == "tr" and self.in_row:
            self.in_row = False
            self.consumer([" ".join(cell.split()) for cell in self.cells], self.links)
            self.cells, self.links = [], []


def _size(cells: list[str]) -> str | int:
    for cell in cells:
        match = re.fullmatch(r"\d+(?:[.,]\d+)?\s*[KMGTPE]?i?B", cell, re.IGNORECASE)
        if match:
            return match.group().replace(",", ".")
    return -1


def _cell(cells: list[str], position: int) -> str:
    return cells[position] if 0 <= position < len(cells) else ""


def _detail_url(site: str, href: str) -> str:
    try:
        candidate = _http(urljoin(site, href))
        if candidate and urlsplit(candidate).netloc == urlsplit(site).netloc:
            return candidate
    except ValueError:
        pass
    return ""


@final
class uindex:
    url = "https://uindex.org"
    name = "UIndex"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "1",
        "tv": "2",
        "games": "3",
        "music": "4",
        "software": "5",
        "anime": "7",
    }

    def search(self, what: str, cat: str = "all") -> None:
        _ = _qbt_new_deadline()
        query = quote(unquote(what).strip()[:200], safe="")
        if not query or cat not in self.supported_categories:
            return
        endpoint = f"{self.url}/search.php?search={query}&c={self.supported_categories[cat]}"
        seen: set[str] = set()

        def consume(cells: list[str], links: list[tuple[int, str, str]]) -> None:
            details = [
                (url, title)
                for _, href, title in links
                if (url := _detail_url(self.url, href))
                and ("/details.php" in url or "/torrent/" in url)
            ]
            detail, title = details[0] if details else (self.url, "")
            for _, href, name in links:
                if href.lower().startswith("magnet:"):
                    _ = _emit(
                        self.url,
                        seen,
                        title or name,
                        href,
                        "",
                        _size(cells),
                        _cell(cells, 4).replace(",", ""),
                        _cell(cells, 5).replace(",", ""),
                        detail,
                    )
                    break

        _Rows(consume).feed(_read(endpoint))
