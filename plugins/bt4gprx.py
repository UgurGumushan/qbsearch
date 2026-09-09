# VERSION: 2.0
"""bt4gprx engine: movies, TV, music, books and software torrents.

Download links are redirects through a third-party domain, so the engine
follows each one and rebuilds a magnet from the torrent hash plus a public
tracker list.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import urljoin

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


class bt4gprx:
    url: str = "https://bt4gprx.com/"
    name: str = "bt4gprx"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "",
        "movies": "movie/",
        "tv": "movie/",
        "music": "audio/",
        "books": "doc/",
        "software": "app/",
    }

    def __init__(self) -> None:
        self.trackerlist: list[str] = []

    class MyHTMLParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.is_in_container: bool = False
            self.is_in_entry: bool = False
            self.b_value: str = ""
            self.container_row_count: int = 0
            self.temp_result: dict[str, str] = {}
            self.results: list[dict[str, str]] = []

        def parse(self, feed: str) -> list[dict[str, str]]:
            super().feed(feed)
            return self.results

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            attr_dict = {key: value for key, value in attrs if value is not None}
            if tag == "div":
                if not self.is_in_container and attr_dict.get("class", "") == "container":
                    self.is_in_container = True
            elif tag == "a":
                if self.is_in_container and all(x in attr_dict for x in ["title", "href"]):
                    self.is_in_entry = True
                    self.temp_result.update(attr_dict)
            elif tag == "b" and self.is_in_entry:
                classname = attr_dict.get("class") or ""
                idname = attr_dict.get("id") or ""
                self.b_value = "filesize" if "cpill" in classname else idname

        @override
        def handle_endtag(self, tag: str) -> None:
            if tag == "div":
                self.is_in_entry = False

        @override
        def handle_data(self, data: str) -> None:
            if self.b_value != "":
                self.temp_result[self.b_value] = data
                if self.b_value == "leechers":
                    self.results.append(self.temp_result)
                    self.temp_result = {}
                self.b_value = ""

    def search(self, term: str, cat: str = "all") -> None:
        pagenumber = 1
        all_results: list[dict[str, str]] = []
        for _ in range(MAX_PAGES):
            result_page = self.search_page(term, pagenumber, cat)
            if result_page:
                all_results.extend(result_page)
            else:
                break
            pagenumber = pagenumber + 1
        self.pretty_print_results(all_results)

    def search_page(self, term: str, pagenumber: int, cat: str) -> list[dict[str, str]]:
        try:
            query = (
                f"{self.url}{self.supported_categories[cat]}search/{term}/byseeders/{pagenumber}"
            )
            parser = self.MyHTMLParser()
            return parser.parse(retrieve_url(query))
        except Exception:
            return []

    def _load_trackerlist(self) -> list[str]:
        if self.trackerlist:
            return self.trackerlist
        try:
            parsed = json.loads(retrieve_url("https://downloadtorrentfile.com/trackerlist"))
        except (TypeError, ValueError):
            return []
        if not isinstance(parsed, list):
            return []
        self.trackerlist = [str(tracker) for tracker in parsed if tracker]
        return self.trackerlist

    def _resolve_magnet(self, info: str, trackerlist: list[str]) -> str | None:
        content = retrieve_url(info)
        match = re.search(r'href="//(downloadtorrentfile.com/hash/[^"]+)', content)
        if not match:
            return None
        actual_link = "https:" + match.group(0)
        try:
            hash_value = actual_link.split("/hash/")[1].split("?")[0]
            name_value = actual_link.split("?name=")[1]
        except (IndexError, ValueError):
            return None
        return f"magnet:?xt=urn:btih:{hash_value}&dn={name_value}&tr=" + "&tr=".join(
            trackerlist
        )

    def download_torrent(self, info: str) -> str | None:
        try:
            trackerlist = self._load_trackerlist()
            if not trackerlist:
                print("Failed to find downloadtorrentfile.com link.")
                return
            magnet = self._resolve_magnet(info, trackerlist)
            if magnet is None:
                print("Failed to find downloadtorrentfile.com link.")
                return
            return magnet
        except (TypeError, ValueError, IndexError) as e:
            print(f"Error extracting downloadtorrentfile.com link: {e}")
            return

    def _resolve_result(
        self, index: int, result: dict[str, str], trackerlist: list[str]
    ) -> tuple[int, SearchResults | None]:
        href = result.get("href", "")
        if not href:
            return index, None
        magnet_link = self._resolve_magnet(urljoin(self.url, href), trackerlist)
        if magnet_link is None:
            return index, None
        try:
            seeders = int(result.get("seeders", "-1"))
        except ValueError:
            seeders = -1
        try:
            leechers = int(result.get("leechers", "-1"))
        except ValueError:
            leechers = -1
        return index, {
            "name": result.get("title", ""),
            "size": result.get("filesize", ""),
            "seeds": seeders,
            "leech": leechers,
            "engine_url": self.url,
            "link": magnet_link,
        }

    def pretty_print_results(self, results: list[dict[str, str]]) -> None:
        if not results:
            return

        def seed_count(result: dict[str, str]) -> int:
            try:
                return int(result.get("seeders", "-1"))
            except ValueError:
                return -1

        sorted_results = sorted(results, key=seed_count, reverse=True)
        jobs: list[tuple[int, dict[str, str], list[str]]] = []
        seen_hrefs: set[str] = set()
        trackerlist = self._load_trackerlist()
        if not trackerlist:
            return
        for index, result in enumerate(sorted_results):
            href = result.get("href", "")
            if not href or href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            jobs.append((index, result, trackerlist))
            if len(jobs) >= MAX_DETAILS:
                break

        resolved = _qbt_run_parallel(self._resolve_result, jobs, _qbt_new_deadline())
        for _, torrent_info in sorted(resolved, key=lambda item: item[0]):
            if torrent_info is not None:
                _qbt_prettyPrinter(torrent_info)
