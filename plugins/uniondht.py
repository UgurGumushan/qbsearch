# VERSION: 1.2
"""
UnionDHT (http://uniondht.org) search engine. DHT tracker front-end: scrapes
the tracker page in batches of 50 and emits parsed rows after each bounded
search.  Output is serialized by the generated safety preamble.
"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import ClassVar

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import prettyPrinter

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


TorrentInfo = dict[str, str]


class uniondht:
    name: str = "UnionDHT"
    url: str = "http://uniondht.org"
    supported_categories: ClassVar[dict[str, str]] = {"all": ""}

    class UnionDHTParser(HTMLParser):
        def __init__(self, url: str):
            super().__init__()
            self.engine_url: str = url
            self.torrent_info: TorrentInfo = self.default_torrent_info()
            self.results: list[TorrentInfo] = []
            self.total_results: int = 0
            self.find_total_results: bool = True
            self.find_torrent: bool = False
            self.find_desc_link: bool = False
            self.find_name: bool = False
            self.find_link: bool = False
            self.find_seeds: bool = False
            self.find_leech_class: bool = False
            self.find_leech: bool = False
            self.parse_total_results: bool = False
            self.parse_name: bool = False
            self.parse_size: bool = False
            self.parse_seeds: bool = False
            self.parse_leech: bool = False
            self.print_result: bool = False
            self.seen_links: set[str] = set()

        def default_torrent_info(self) -> TorrentInfo:
            return {
                "link": "",
                "name": "",
                "size": "-1",
                "seeds": "-1",
                "leech": "-1",
                "engine_url": self.engine_url,
                "desc_link": "",
            }

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
            if self.find_total_results:
                if tag == "p":
                    attributes = dict(attrs)
                    if "class" in attributes and attributes["class"] == "floatR":
                        self.find_total_results = False
                        self.parse_total_results = True
            elif self.find_torrent:
                if tag == "tr":
                    attributes = dict(attrs)
                    if "id" in attributes and (attributes["id"] or "").startswith("tor"):
                        self.find_torrent = False
                        self.find_desc_link = True
            elif self.find_desc_link:
                if tag == "a":
                    attributes = dict(attrs)
                    if "href" in attributes and (attributes["href"] or "").startswith("/topic"):
                        self.torrent_info["desc_link"] = self.engine_url + (
                            attributes["href"] or ""
                        )
                        self.find_desc_link = False
                        self.find_name = True
            elif self.find_name:
                if tag == "b":
                    self.find_name = False
                    self.parse_name = True
            elif self.find_link:
                if tag == "wbr":
                    self.find_link = False
                    self.parse_name = True
                elif tag == "a":
                    attributes = dict(attrs)
                    if "href" in attributes and (attributes["href"] or "").startswith("/dl."):
                        self.torrent_info["link"] = self.engine_url + (attributes["href"] or "")
                        self.find_link = False
                        self.parse_size = True
            elif self.find_seeds:
                if tag == "td":
                    attributes = dict(attrs)
                    if "class" in attributes and (attributes["class"] or "").find("seed") != -1:
                        self.find_seeds = False
                        self.parse_seeds = True
            elif self.find_leech_class:
                if tag == "td":
                    attributes = dict(attrs)
                    if "class" in attributes and (attributes["class"] or "").find("leech") != -1:
                        self.find_leech_class = False
                        self.find_leech = True
            elif self.find_leech and tag == "b":
                self.find_leech = False
                self.parse_leech = True

        @override
        def handle_data(self, data: str):
            if self.parse_total_results:
                total_results = data.split(":")[1].split("(")[0].strip()
                self.total_results = int(total_results)
                self.parse_total_results = False
                self.find_torrent = True
            elif self.parse_name:
                self.torrent_info["name"] += data.strip()
                self.parse_name = False
                self.find_link = True
            elif self.parse_size:
                self.torrent_info["size"] = data.replace("\xa0", "").strip()
                self.parse_size = False
                self.find_seeds = True
            elif self.parse_seeds:
                self.torrent_info["seeds"] = data.strip()
                self.parse_seeds = False
                self.find_leech_class = True
            elif self.parse_leech:
                self.torrent_info["leech"] = data.strip()
                self.parse_leech = False
                self.print_result = True

        @override
        def handle_endtag(self, tag: str):
            if self.print_result:
                result_link = self.torrent_info.get("link") or self.torrent_info.get("desc_link")
                if result_link and result_link not in self.seen_links:
                    self.seen_links.add(result_link)
                    self.results.append(self.torrent_info.copy())
                self.torrent_info = self.default_torrent_info()
                self.print_result = False
                self.find_torrent = True

    def search(self, what: str, _cat: str = "all"):
        parser = self.UnionDHTParser(self.url)
        for page_number in range(1, MAX_PAGES + 1):
            torrent_count = (page_number - 1) * 50
            search_url = f"{self.url}/tracker.php?nm={what}&start={torrent_count}"
            try:
                retrieved_page = retrieve_url(search_url)
                if not retrieved_page:
                    break
                before = len(parser.results)
                parser.feed(retrieved_page)
            except Exception:
                break
            if len(parser.results) == before:
                break
            if parser.total_results and torrent_count + 50 >= parser.total_results:
                break
        parser.close()
        for result in parser.results:
            _qbt_prettyPrinter(result)


if __name__ == "__main__":
    engine = uniondht()
    engine.search("ubuntu")
