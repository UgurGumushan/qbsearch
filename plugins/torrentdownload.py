# VERSION: 1.1
"""
TorrentDownload (https://www.torrentdownload.info) search engine. Scrape-based;
the info hash is read from the href of each row's title link to build the
magnet. Up to 10 pages are fetched sequentially with a short delay between.
"""

from __future__ import annotations

import re
from typing import cast

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


class torrentdownload:
    url: str = "https://www.torrentdownload.info/"
    name: str = "TorrentDownload"
    max_pages: int = 10

    class HTMLParser:
        def __init__(self, url: str):
            self.url: str = url
            self.pageResSize: int = 0
            self.seen_info_hashes: set[str] = set()

        def feed(self, html: str):
            self.pageResSize = 0
            torrents = self.__findTorrents(html)
            resultSize = len(torrents)
            if resultSize == 0:
                return
            else:
                self.pageResSize = resultSize
            for torrent in range(min(resultSize, MAX_DETAILS)):
                data: SearchResults = {
                    "link": torrents[torrent][0],
                    "name": torrents[torrent][1],
                    "size": torrents[torrent][2],
                    "seeds": int(torrents[torrent][3]),
                    "leech": int(torrents[torrent][4]),
                    "engine_url": self.url,
                    "desc_link": torrents[torrent][5],
                }
                _qbt_prettyPrinter(data)

        def __findTorrents(self, html: str) -> list[list[str]]:
            torrents: list[list[str]] = []
            trs = cast(list[str], re.findall(r"<tr><td.+?tt-name.+?</tr>", html))
            for tr in trs:
                # Extract from the A node all the needed information
                url_titles = re.search(
                    r".+?href=\"/(.+?)\">(.+?)</a>.+?tdnormal\">([0-9\,\.]+ (TB|GB|MB|KB)).+?tdseed\">([0-9,]+).+?tdleech\">([0-9,]+)",
                    tr,
                )
                if url_titles:
                    info_hash = url_titles.group(1).split("/")[0]
                    if not info_hash or info_hash in self.seen_info_hashes:
                        continue
                    self.seen_info_hashes.add(info_hash)
                    torrent_data = [
                        f"magnet:?xt=urn:btih:{info_hash}&dn=&tr=udp%3A%2F%2Ftracker.torrent.eu.org%3A451%2Fannounce&tr=http%3A%2F%2Ftracker.ipv6tracker.ru%3A80%2Fannounce&tr=udp%3A%2F%2Fretracker.hotplug.ru%3A2710%2Fannounce&tr=https%3A%2F%2Ftracker.fastdownload.xyz%3A443%2Fannounce&tr=https%3A%2F%2Fopentracker.xyz%3A443%2Fannounce&tr=http%3A%2F%2Fopen.trackerlist.xyz%3A80%2Fannounce&tr=udp%3A%2F%2Ftracker.birkenwald.de%3A6969%2Fannounce&tr=https%3A%2F%2Ft.quic.ws%3A443%2Fannounce&tr=https%3A%2F%2Ftracker.parrotsec.org%3A443%2Fannounce&tr=udp%3A%2F%2Ftracker.supertracker.net%3A1337%2Fannounce&tr=http%3A%2F%2Fgwp2-v19.rinet.ru%3A80%2Fannounce&tr=udp%3A%2F%2Fbigfoot1942.sektori.org%3A6969%2Fannounce&tr=udp%3A%2F%2Fcarapax.net%3A6969%2Fannounce&tr=udp%3A%2F%2Fretracker.akado-ural.ru%3A80%2Fannounce&tr=udp%3A%2F%2Fretracker.maxnet.ua%3A80%2Fannounce&tr=udp%3A%2F%2Fbt.dy20188.com%3A80%2Fannounce&tr=http%3A%2F%2F0d.kebhana.mx%3A443%2Fannounce&tr=http%3A%2F%2Ftracker.files.fm%3A6969%2Fannounce&tr=http%3A%2F%2Fretracker.joxnet.ru%3A80%2Fannounce&tr=http%3A%2F%2Ftracker.moxing.party%3A6969%2Fannounce",
                        url_titles.group(2).replace('<span class="na">', "").replace("</span>", ""),
                        url_titles.group(3).replace(",", ""),
                        url_titles.group(5).replace(",", ""),
                        url_titles.group(6).replace(",", ""),
                        f"{self.url}{url_titles.group(1)}",
                    ]
                    torrents.append(torrent_data)
            return torrents

    def download_torrent(self, download_url: str):
        print(download_url + " " + download_url)

    def search(self, what: str, _cat: str = "all"):
        what = what.replace("%20", "+")
        parser = self.HTMLParser(self.url)
        for currPage in range(1, min(self.max_pages, MAX_PAGES) + 1):
            url = f"{self.url}search?q={what}&p={currPage}"
            # Some replacements to format the html source
            html = re.sub(r"\s+", " ", retrieve_url(url)).strip()
            parser.feed(html)
            if parser.pageResSize <= 0:
                break
