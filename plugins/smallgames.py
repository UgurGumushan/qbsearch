# VERSION: 1.03
"""
small-games.info search engine. Not every result links a torrent file
directly: open the description link for the game page, and if it offers a
mediaget button, append &direct=1 to that link to get the .torrent.
"""

from __future__ import annotations

import os
import re
import ssl
import tempfile
from typing import ClassVar, cast

from novaprinter import SearchResults, prettyPrinter

_qbt_helper_retrieve_url = None
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


# noinspection PyPep8Naming
SEARCH_RESULT_RE = re.compile(
    '<a title="(.*?)"\\shref="/.*?i=(\\d*).*?Скачать\\sигру\\s\\((.{2,11})\\)'
)
NAME_CLEAN_RE = re.compile("[A-Za-z0-9].*")


class smallgames:
    url: str = "http://small-games.info/"
    name: str = "small-games.info"
    result: ClassVar[SearchResults] = {
        "name": "",
        "link": "",
        "size": "",
        "seeds": -1,
        "leech": -1,
        "engine_url": url,
    }
    supported_categories: ClassVar[dict[str, bool]] = {"all": True, "games": True}

    def download_torrent(self, url: str) -> None:
        file, path = tempfile.mkstemp(".torrent")
        file = os.fdopen(file, "wb")

        dat = self.get_url(url)
        data = dat.decode("utf-8", "replace")
        if data == "No link found!" or data == "some error":
            return
        else:
            # Write it to a file
            _ = file.write(dat)
            file.close()
            # return file path
            print(path + " " + url)

    def search(self, what: str, _cat: str = "all") -> None:
        query = "https://small-games.info/?go=search&go=search&search_text=" + what
        data = self.get_url(query).decode("utf-8", "replace")
        results = cast(list[tuple[str, str, str]], SEARCH_RESULT_RE.findall(data))
        seen_gids: set[str] = set()

        for res in results:
            if len(seen_gids) >= MAX_DETAILS or res[1] in seen_gids:
                if len(seen_gids) >= MAX_DETAILS:
                    break
                continue
            name_match = NAME_CLEAN_RE.search(res[0])
            if name_match is None:
                continue
            seen_gids.add(res[1])
            result = self.result.copy()
            result["name"] = name_match.group(0)
            result["link"] = self.url + "getTorrent.php?direct=1&gid=" + res[1]
            result["desc_link"] = self.url + "?go=game&c=61&i=" + res[1]
            #  it always MB, and the M from the string is a weird russian one
            #  so pretty printer will not recognize it
            result["size"] = res[2][:-3] + "MB"
            _qbt_prettyPrinter(result)

    @staticmethod
    def get_url(url: str) -> bytes:
        context = ssl.create_default_context()
        with _qbt_safe_urlopen(url, context=context) as response:
            return response.read()


if __name__ == "__main__":
    engine = smallgames()
    engine.search("eco")
