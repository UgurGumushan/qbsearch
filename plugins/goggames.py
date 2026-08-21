# VERSION: 1.0
"""
GOG-Games game search. Queries the site's REST API and builds magnet links
from the infohash; entries without a torrent are listed with a "No torrent"
note and the site URL as their download link.
"""

from __future__ import annotations

import datetime
import json
import ssl
import urllib.parse
import urllib.request
from typing import ClassVar, cast

from novaprinter import SearchResults, prettyPrinter

_qbt_helper_retrieve_url = None
# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from collections.abc import Iterable as _QBTIterable
    from concurrent.futures import Future as _QBTFuture
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
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


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

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


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation: _QBTCallable[[], object]) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
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
        if attempt + 1 < max(1, int(MAX_ATTEMPTS)):
            _qbt_sleep(attempt)
    return ""


def _qbt_safe_urlopen(
    url: object,
    data: object | None = None,
    *,
    context: object | None = None,
) -> _QBTResponseContext:
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _qbt_empty_response(url)
        response: _QBTResponseContext | None = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen_typed(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen_typed(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = response.status
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status >= 400:
                response.close()
                return _qbt_empty_response(url)
            return response
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
            # A malformed request is not useful to retry, but it must not
            # abort the qBittorrent search process.
            return _qbt_empty_response(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
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
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures: list[_QBTFuture[_QBTJobResult]] = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results: list[_QBTJobResult] = []
    try:
        remaining = max(0.0, deadline - _qbt_time.monotonic())
        for future in _qbt_as_completed(futures, timeout=remaining):
            try:
                results.append(future.result())
            except Exception:
                # One dead site/detail page must not discard other results.
                pass
    except _qbt_FuturesTimeoutError:
        for future in futures:
            _ = future.cancel()
    finally:
        try:
            _ = executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            _ = executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# These hooks are available to standalone engines even when a particular
# engine does not call every optional adapter directly.
__all__ = [
    "_qbt_new_deadline",
    "_qbt_prettyPrinter",
    "_qbt_run_parallel",
    "_qbt_safe_urlopen",
    "retrieve_url",
]


# END GENERATED QBITT SAFETY PREAMBLE


_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None

_qbt_helper_retrieve_url = None


def _extract_items(data: object) -> list[dict[str, object]]:
    """Return only object entries from either supported API response shape."""
    raw_items: object = data
    if isinstance(data, dict):
        raw_items = cast(dict[str, object], cast(object, data)).get("data", [])
    if not isinstance(raw_items, list):
        return []
    items: list[dict[str, object]] = []
    for raw_item in cast(list[object], cast(object, raw_items)):
        if isinstance(raw_item, dict):
            items.append(cast(dict[str, object], cast(object, raw_item)))
    return items


class goggames:
    url: str = "https://gog-games.to"

    name: str = "GOG-Games"
    supported_categories: ClassVar[dict[str, str]] = {"all": "0"}

    def search(self, what: str, _cat: str = "all") -> None:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        query_text = urllib.parse.unquote(what).strip().lower()

        # Non-word queries just list the newest torrents
        if query_text in [".", "*", "!"]:
            endpoint = f"{self.url}/api/web/recent-torrents"
            modo = "NOVEDADES"
        else:
            query_encoded = urllib.parse.quote(query_text)
            endpoint = (
                f"{self.url}/search?page=1&search={query_encoded}&sort_by=lastUpdateDescending"
            )
            modo = "BÚSQUEDA"

        req = urllib.request.Request(
            endpoint,
            headers={
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
        )
        data: object = []

        try:
            with _qbt_safe_urlopen(req, context=ctx) as response:
                data = cast(object, json.loads(response.read().decode("utf-8")))
        except Exception:
            return

        # The API answers a bare list, or a dict wrapping the list in "data"
        items = _extract_items(data)

        if not items:
            _qbt_prettyPrinter(
                SearchResults(
                    link=self.url,
                    name="NO SE ENCONTRARON RESULTADOS",
                    size="0",
                    seeds=0,
                    leech=0,
                    engine_url=self.url,
                    desc_link=self.url,
                )
            )
            return

        for item in items:
            try:
                title_original = str(item.get("title", "Juego Desconocido"))
                # Drop non-ASCII leftovers and the '|' separator used as a title delimiter
                title_limpio = title_original.encode("ascii", "ignore").decode("ascii")
                title_limpio = title_limpio.replace("|", "-")

                # Newest-torrents queries get the query symbol prefixed, e.g. "[.] Game"
                if modo == "NOVEDADES":
                    title_final = f"[{query_text}] {title_limpio}"
                else:
                    title_final = title_limpio

                # Publish date: prefer torrent_date, fall back to last_update;
                # skip nulls and keep '-1' so qBitt treats it as unknown
                pub_date_str = -1
                try:
                    if item.get("torrent_date"):
                        clean_date = str(item["torrent_date"]).split(".")[0].replace("T", " ")
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = int(dt.timestamp())
                    elif item.get("last_update") and str(item.get("last_update")).lower() != "null":
                        clean_date = str(item["last_update"]).split(".")[0].replace("T", " ")
                        dt = datetime.datetime.strptime(clean_date, "%Y-%m-%d %H:%M:%S")
                        pub_date_str = int(dt.timestamp())
                except Exception:
                    pass

                # With an infohash the link is a magnet; without one, flag the
                # entry as torrent-less and point at the site instead
                infohash = item.get("infohash")

                if not isinstance(infohash, str) or not infohash:
                    title_final = f"{title_final} - No torrent"
                    enlace_descarga = self.url
                else:
                    encoded_name = urllib.parse.quote(title_final)
                    enlace_descarga = f"magnet:?xt=urn:btih:{infohash}&dn={encoded_name}"

                slug = item.get("slug", "")
                slug_text = slug if isinstance(slug, str) else str(slug)
                res: SearchResults = {
                    "name": title_final,
                    "size": "-1",
                    "seeds": -1,
                    "leech": -1,
                    "engine_url": self.url,
                    "desc_link": f"{self.url}/game/{slug_text}",
                    "pub_date": pub_date_str,
                    "link": enlace_descarga,
                }

                _qbt_prettyPrinter(res)

            except Exception:
                continue
