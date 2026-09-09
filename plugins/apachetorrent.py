# VERSION: 1.00
"""ApacheTorrent (Portuguese-Brazilian, apachetorrent.com).

Movies, series and anime with Portuguese audio (dubbed, dual audio or
subtitled). The engine is magnet-only: it opens each torrent page to read
the magnets, so sizes and peer counts are unavailable (-1).
"""

from __future__ import annotations

import html
import re
import sys
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import quote_plus, unquote, urljoin

from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

_WHITESPACE_RE = re.compile(r"\s+")
_DOWNLOAD_SUFFIX_RE = re.compile(r"\s*Download\s*$", re.IGNORECASE)
_BAIXAR_PREFIX_RE = re.compile(r"^BAIXAR\s+", re.IGNORECASE)
_MAGNET_DN_RE = re.compile(r"[?&]dn=([^&]+)")

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


class apachetorrent:
    url: str = "https://apachetorrent.com"
    name: str = "ApacheTorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "all",
        "anime": "anime",
        "movies": "filmes",
        "tv": "series",
    }

    class SearchResultsParser(HTMLParser):
        def __init__(self, base_url: str) -> None:
            HTMLParser.__init__(self)
            self.base_url: str = base_url
            self.results: list[dict[str, str]] = []

            self.inside_card: bool = False
            self.inside_title_link: bool = False
            self.current_link: str = ""
            self.current_title: str = ""
            self.current_title_attr: str = ""

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == "div" and "capaname" in self._get(params, "class"):
                self.inside_card = True
                self.current_link = ""
                self.current_title = ""
                self.current_title_attr = ""
                return

            if not self.inside_card:
                return

            if tag == "a":
                href = self._get(params, "href")
                title = self._get(params, "title")

                if href and self._is_result_link(href):
                    self.current_link = urljoin(self.base_url, href)

                    if title:
                        self.current_title_attr = self._clean_title(title)

                    self.inside_title_link = True

        @override
        def handle_data(self, data: str) -> None:
            if self.inside_card and self.inside_title_link:
                text = self._clean_text(data)

                if text:
                    if self.current_title:
                        self.current_title += " "
                    self.current_title += text

        @override
        def handle_endtag(self, tag: str) -> None:
            if tag == "a" and self.inside_title_link:
                self.inside_title_link = False

            if tag == "div" and self.inside_card:
                title = self._clean_title(self.current_title or self.current_title_attr)

                if self.current_link and title:
                    self.results.append(
                        {
                            "title": title,
                            "desc_link": self.current_link,
                        }
                    )

                self.inside_card = False
                self.current_link = ""
                self.current_title = ""
                self.current_title_attr = ""

        def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            result: dict[str, str] = {}

            for key, value in attrs:
                result[key] = value if value is not None else ""

            return result

        def _get(self, params: Mapping[str, str], key: str) -> str:
            return params.get(key, "")

        def _is_result_link(self, href: str) -> bool:
            if not href:
                return False

            href_lower = href.lower()

            if not href_lower.startswith("http"):
                return False

            if not href_lower.startswith(self.base_url):
                return False

            return "baixar-torrent" in href_lower

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = _WHITESPACE_RE.sub(" ", text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = _DOWNLOAD_SUFFIX_RE.sub("", title)
            title = _WHITESPACE_RE.sub(" ", title)
            return title.strip()

    class MagnetLinksParser(HTMLParser):
        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.magnets: list[dict[str, str]] = []
            self.seen_magnets: set[str] = set()

            self.inside_download_area: bool = False
            self.current_context: str = ""
            self.capture_text: bool = False

        @override
        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == "div" and params.get("id") == "lista_links":
                self.inside_download_area = True
                return

            if not self.inside_download_area:
                return

            if tag == "p":
                self.capture_text = True
                self.current_context = ""

            if tag == "a":
                href = params.get("href", "")
                title = params.get("title", "")

                if href.startswith("magnet:?") and href not in self.seen_magnets:
                    self.seen_magnets.add(href)
                    self.magnets.append(
                        {
                            "magnet": html.unescape(href),
                            "title": self._clean_title(title or self.current_context),
                        }
                    )

        @override
        def handle_data(self, data: str) -> None:
            if self.inside_download_area and self.capture_text:
                text = self._clean_text(data)

                if text:
                    if self.current_context:
                        self.current_context += " "
                    self.current_context += text

        @override
        def handle_endtag(self, tag: str) -> None:
            if tag == "p" and self.capture_text:
                self.capture_text = False
                self.current_context = ""

            if tag == "div" and self.inside_download_area:
                self.inside_download_area = False

        def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            result: dict[str, str] = {}

            for key, value in attrs:
                result[key] = value if value is not None else ""

            return result

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = _WHITESPACE_RE.sub(" ", text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = _BAIXAR_PREFIX_RE.sub("", title)
            title = _WHITESPACE_RE.sub(" ", title)
            return title.strip()

    def search(self, what: str, cat: str = "all") -> None:
        search_url = self._build_search_url(what, cat)

        try:
            search_html = retrieve_url(search_url)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Apache Torrent search request failed: {exc}", file=sys.stderr)
            return

        search_parser = self.SearchResultsParser(self.url)
        search_parser.feed(search_html)
        search_parser.close()

        jobs: list[tuple[int, dict[str, str]]] = []
        seen_desc_links: set[str] = set()
        for index, result in enumerate(search_parser.results):
            desc_link = result.get("desc_link", "")
            if not desc_link or desc_link in seen_desc_links:
                continue
            seen_desc_links.add(desc_link)
            jobs.append((index, result))
            if len(jobs) >= MAX_DETAILS:
                break

        resolved = _qbt_run_parallel(self._fetch_result_magnets, jobs, _qbt_new_deadline())
        for _, torrent_items in sorted(resolved, key=lambda item: item[0]):
            for torrent_info in torrent_items:
                _qbt_prettyPrinter(torrent_info)

    def _build_search_url(self, what: str, cat: str) -> str:
        query = what.replace("%20", "+")

        if cat not in self.supported_categories:
            cat = "all"

        return self.url + "/index.php?s=" + quote_plus(query).replace("%2B", "+")

    def _fetch_result_magnets(
        self, index: int, result: dict[str, str]
    ) -> tuple[int, list[SearchResults]]:
        desc_link = result.get("desc_link", "")
        base_title = result.get("title", "").strip()
        torrent_items: list[SearchResults] = []

        if not desc_link:
            return index, torrent_items

        try:
            details_html = retrieve_url(desc_link)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Apache Torrent details request failed: {exc}", file=sys.stderr)
            return index, torrent_items

        magnet_parser = self.MagnetLinksParser()
        magnet_parser.feed(details_html)
        magnet_parser.close()

        for magnet_item in magnet_parser.magnets:
            magnet = magnet_item.get("magnet", "")
            magnet_title = magnet_item.get("title", "")

            if not magnet:
                continue

            name = self._build_result_name(base_title, magnet_title, magnet)

            torrent_info: SearchResults = {
                "link": magnet,
                "name": name,
                "size": "-1",
                "seeds": -1,
                "leech": -1,
                "engine_url": self.url,
                "desc_link": desc_link,
                "pub_date": -1,
            }

            torrent_items.append(torrent_info)

        return index, torrent_items

    def _build_result_name(self, base_title: str, magnet_title: str, magnet: str) -> str:
        if magnet_title:
            return base_title + " - " + magnet_title

        magnet_name = self._extract_magnet_dn(magnet)

        if magnet_name:
            return base_title + " - " + magnet_name

        return base_title

    def _extract_magnet_dn(self, magnet: str) -> str:
        match = _MAGNET_DN_RE.search(magnet)

        if not match:
            return ""

        name = unquote(match.group(1))
        name = name.replace(".", " ")
        name = _WHITESPACE_RE.sub(" ", name)

        return name.strip()
