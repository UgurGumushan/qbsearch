# VERSION: 1.6
"""Elitetorrent (Spanish) engine: movie and TV series torrents.

The magnet link stored on each torrent page is obfuscated with repeated
Base64 plus ROT13 layers, which this engine reverses before printing.
"""

from __future__ import annotations

import base64
import codecs
import re
from datetime import datetime
from typing import ClassVar, TypedDict, cast

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
    from typing import Callable as _QBTCallable
    from typing import Protocol as _QBTProtocol
    from typing import TypeVar as _QBTTypeVar
    from typing import cast as _qbt_cast
    from urllib.request import urlopen as _qbt_urlopen
except ImportError as error:
    raise RuntimeError("qBittorrent safety preamble requires Python stdlib") from error

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


MAX_DEPTH = 10  # Safety cap on how many Base64+ROT13 layers to peel off.


class TorrentInfo(TypedDict):
    title: str | None
    link: list[str] | str | None
    size: str
    quality: str | None
    language: str | None
    date: str | int
    seeds: str | int
    leech: str | int
    formatted_name: str


def deobfuscate_magnet(obfuscated: str) -> str | None:
    encoded = obfuscated.encode()
    try:
        for _ in range(MAX_DEPTH):
            decoded_bytes = base64.b64decode(encoded)
            decoded_value = codecs.decode(decoded_bytes.decode(encoding="utf-8"), "rot_13")
            if "magnet" in decoded_value:
                return decoded_value
            encoded = decoded_bytes
    except Exception:
        return None
    return None


def format_info(info: TorrentInfo) -> None:
    links = info["link"]
    if isinstance(links, list):
        # The site normally includes a second matching attribute; accept the
        # first one as a safe fallback when a page contains only one.
        encoded_link = links[1] if len(links) > 1 else links[0] if links else None
        info["link"] = (
            deobfuscate_magnet(encoded_link.lstrip("i=").rstrip('"'))
            if encoded_link is not None
            else None
        )
    else:
        info["link"] = None

    title = info["title"] or ""
    if title.startswith("<h1>") and title.endswith("</h1>"):
        title = title[4:-5]
    if title.startswith("Descargar ") and title.endswith(" por torrent"):
        title = title[10:-12].strip()

    formatted_name = title
    if info["language"] is not None:
        formatted_name += " [{}]".format(info["language"])
    if info["quality"] is not None:
        formatted_name += " {} ".format(info["quality"])
    formatted_name += "({})".format(info["date"])
    info["formatted_name"] = formatted_name


class elitetorrent:
    url: str = "https://www.elitetorrent.com"
    name: str = "Elitetorrent"
    # Page has only movies and tv series. Search box has no filters
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "0",
        "movies": "peliculas",
        "tv": "series",
    }

    def __init__(self) -> None:
        self.pages_limit: int = 2  # Limit of pages, more pages increase the time it takes

    def download_torrent(self, info: SearchResults) -> None:
        """Unused: results already carry ready-to-use magnet links."""
        print(download_file(info["link"]))

    def parse_result(self, url: str) -> SearchResults | None:
        data = retrieve_url(url).replace("\n", "")
        info: TorrentInfo = {
            "title": None,
            "link": [],
            "size": "0",
            "quality": None,
            "language": None,
            "date": -1,
            "seeds": -1,
            "leech": -1,
            "formatted_name": "",
        }
        m_title = re.search(r"<h1>Descargar .+ por torrent</h1>", data)
        info["title"] = m_title.group(0) if m_title else None
        info["link"] = re.findall(r"i=[-A-Za-z0-9+/]+\={0,3}\"", data)
        m = re.search(r"Tama.?o:</b> [0-9\.]+[\ GM]+B", data)
        info["size"] = m.group(0).split("</b>")[1].strip() if m else "0"
        m = re.search(r"Calidad:</b> [0-9\.a-z\-]+", data)
        info["quality"] = m.group(0).removeprefix("Calidad:</b>").strip() if m else None
        m = re.search(r"Idioma:</b>[a-zA-Zñ\ ]+", data)
        info["language"] = m.group(0).removeprefix("Idioma:</b>").strip() if m else None
        m = re.search(r"Fecha:</b>[\ 0-9\-]+", data)
        info["date"] = m.group(0).replace(" ", "").removeprefix("Fecha:</b>") if m else -1
        m = re.search(r"<b>Semillas</b>:[\ 0-9]*", data)
        info["seeds"] = m.group(0).split(":")[-1].strip() if m else -1
        m = re.search(r"<b>Clientes</b>:[\ 0-9]*", data)
        info["leech"] = m.group(0).split(":")[-1].strip() if m else -1

        format_info(info)
        if info["title"] is None or not isinstance(info["link"], str):
            return None

        pub_date = info["date"]
        if isinstance(pub_date, str):
            # there are 2 format dates: YYYY-MM-DD or DD-MM-YYYY
            if int(pub_date.split("-")[0]) > 1000:
                parsed_date = datetime.strptime(pub_date, "%Y-%m-%d")
            else:
                parsed_date = datetime.strptime(pub_date, "%d-%m-%Y")
            pub_date = round(datetime.timestamp(parsed_date))

        seeds = info["seeds"]
        leech = info["leech"]
        return {
            "seeds": int(seeds)
            if isinstance(seeds, str) and seeds
            else seeds
            if isinstance(seeds, int)
            else -1,
            "leech": int(leech)
            if isinstance(leech, str) and leech
            else leech
            if isinstance(leech, int)
            else -1,
            "name": info["formatted_name"],
            "size": info["size"],
            "desc_link": url,
            "engine_url": self.url,
            "link": info["link"],
            "pub_date": pub_date,
        }

    def search(self, what: str, cat: str = "all") -> None:
        query = what.replace("%20", "+")
        search_url = "{}/?s={}".format(self.url, query)
        html = retrieve_url(search_url)

        # Get number of pages
        number_pages = 0
        if "paginacion" in html:
            pages = cast(list[str], re.findall(r'<a.*?class="pagina.*?</a>', html))
            if len(pages) > 0:
                last_page = pages[-1]
                page_match = re.search(r"page/(\d+)/", last_page)
                if page_match is not None:
                    number_pages = int(page_match.group(1))

        # Only one page but there are results
        elif "Resultado de buscar" in html:
            number_pages = 1
        else:
            # No pagination links and no single-results banner: nothing found.
            number_pages = 0

        # Set number of pages depending by limit
        number_pages = min(self.pages_limit, number_pages)

        links: list[str] = []
        seen_links: set[str] = set()

        for page in range(1, min(number_pages, MAX_PAGES) + 1):
            # Page urls look like: {url}/page/{n}/?s={query}
            url = "{}/page/{}/?s={}".format(self.url, page, query)
            html = retrieve_url(url).replace("\n", "")  # Replace newline to help the regex
            # I hate regex, check if selected category is films or tv, if its 'all' get both
            pattern = (
                rf"({self.url}/series/.*?/|{self.url}/peliculas/.*?/)"
                if cat == "all"
                else rf"{self.url}/{self.supported_categories[cat]}/.*?/"
            )
            # Collect every matching result link on the page.
            items = cast(list[str], re.findall(pattern, html))
            for result_link in items:
                if len(links) >= MAX_DETAILS:
                    break
                if result_link not in seen_links:
                    seen_links.add(result_link)
                    links.append(result_link)
            if len(links) >= MAX_DETAILS:
                break

        jobs = [(link,) for link in links]
        for item in _qbt_run_parallel(self.parse_result, jobs, _qbt_new_deadline()):
            if item is not None:
                # Prints in this format: link|name|size|seeds|leech|engine_url|desc_link|pub_date
                _qbt_prettyPrinter(item)
