# VERSION: 3.20
"""
EZTVX series and movie search. Queries the ezvx.to JSON API by IMDb id when
OMDB resolves the title, otherwise by keyword, paginating 100 items per page.
"""

from __future__ import annotations

import json
import re
from typing import ClassVar, Union, cast

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
from novaprinter import SearchResults, prettyPrinter

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


class eztvx:
    url: str = "https://eztvx.to"
    name: str = "EZTVX"
    supported_categories: ClassVar[dict[str, str]] = {"all": "all", "tv": "tv"}

    OMDB_API_KEY: str = "YOUR_OMDB_API_KEY"  # Get a free key at https://www.omdbapi.com/apikey.aspx

    def __init__(self) -> None:
        pass

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def search(self, what: str, _cat: str = "all") -> None:
        keywords = what.replace("%20", " ").replace(".", " ").replace("-", " ")
        keywords = re.sub(r"\s+", " ", keywords).strip()

        season, episode = self._parse_season_episode(keywords)
        title = self._clean_title(keywords)
        imdb_id = self._get_imdb_id(title)

        if imdb_id:
            self._search_by_imdb(imdb_id, season=season, episode=episode)
        else:
            self._search_by_keywords(title, season=season, episode=episode)

    def _parse_season_episode(self, keywords: str) -> tuple[int | None, int | None]:
        pattern = re.compile(
            r"\b(?:"
            + r"s(\d{1,2})e(\d{1,2})"
            + r"|s(\d{1,2})"
            + r"|e(\d{1,2})"
            + r"|(\d{1,2})x(\d{1,2})"
            + r"|season\s*(\d{1,2})\s*episode\s*(\d{1,2})"
            + r"|season\s*(\d{1,2})"
            + r")\b",
            re.IGNORECASE,
        )
        # Matches S01E02, S01, E02, 1x02, "season 1 episode 2", "season 1"
        season: int | None = None
        episode: int | None = None
        match = pattern.search(keywords)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                season, episode = int(g[0]), int(g[1])
            elif g[2]:
                season = int(g[2])
            elif g[3]:
                episode = int(g[3])
            elif g[4] and g[5]:
                season, episode = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                season, episode = int(g[6]), int(g[7])
            elif g[8]:
                season = int(g[8])
        return season, episode

    def _clean_title(self, keywords: str) -> str:
        episode_pattern = re.compile(
            r"\b(?:"
            + r"s(\d{1,2})e(\d{1,2})"
            + r"|s(\d{1,2})"
            + r"|e(\d{1,2})"
            + r"|(\d{1,2})x(\d{1,2})"
            + r"|season\s*(\d{1,2})\s*episode\s*(\d{1,2})"
            + r"|season\s*(\d{1,2})"
            + r")\b",
            re.IGNORECASE,
        )
        junk_pattern = re.compile(
            r"\b(1080p|720p|480p|2160p|4k|x264|x265|hevc|avc|bluray|"
            + r"webrip|web-dl|hdtv|dvdrip|proper|repack|extended|"
            + r"theatrical|directors\.cut|remux)\b",
            re.IGNORECASE,
        )
        cleaned = episode_pattern.sub("", keywords)
        cleaned = junk_pattern.sub("", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _matches_season_episode(self, title: str, season: int | None, episode: int | None) -> bool:
        if season is None and episode is None:
            return True
        pattern = re.compile(
            r"\b(?:"
            + r"s(\d{1,2})e(\d{1,2})"
            + r"|s(\d{1,2})"
            + r"|e(\d{1,2})"
            + r"|(\d{1,2})x(\d{1,2})"
            + r"|season\s*(\d{1,2})\s*episode\s*(\d{1,2})"
            + r"|season\s*(\d{1,2})"
            + r")\b",
            re.IGNORECASE,
        )
        s: int | None = None
        e: int | None = None
        match = pattern.search(title)
        if match:
            g = match.groups()
            if g[0] and g[1]:
                s, e = int(g[0]), int(g[1])
            elif g[2]:
                s = int(g[2])
            elif g[3]:
                e = int(g[3])
            elif g[4] and g[5]:
                s, e = int(g[4]), int(g[5])
            elif g[6] and g[7]:
                s, e = int(g[6]), int(g[7])
            elif g[8]:
                s = int(g[8])
        if season is not None and episode is None:
            return s == season
        if episode is not None and season is None:
            return e == episode
        return s == season and e == episode

    def _get_imdb_id(self, title: str) -> str | None:
        if not title:
            return None
        imdb_match = re.fullmatch(r"(?:tt)?(\d{7,8})", title, re.IGNORECASE)
        if imdb_match:
            return imdb_match.group(1)
        try:
            omdb_url = "http://www.omdbapi.com/?apikey={}&t={}&type=series".format(
                self.OMDB_API_KEY, title.replace(" ", "+")
            )
            response = retrieve_url(omdb_url)
            data_value: object = cast(object, json.loads(response))
            if isinstance(data_value, dict):
                data = cast(dict[str, object], cast(object, data_value))
                if data.get("Response") == "True":
                    return str(data.get("imdbID", "")).replace("tt", "")
        except Exception:
            pass
        return None

    def _search_by_imdb(
        self, imdb_id: str, season: int | None = None, episode: int | None = None
    ) -> None:
        page = 1
        for _ in range(MAX_PAGES):
            api_url = f"{self.url}/api/get-torrents?limit=100&page={page}&imdb_id={imdb_id}"
            try:
                response = retrieve_url(api_url)
                data_value: object = cast(object, json.loads(response))
            except Exception:
                break
            if not isinstance(data_value, dict):
                break
            data = cast(dict[str, object], cast(object, data_value))

            raw_torrents = data.get("torrents", [])
            if not isinstance(raw_torrents, list) or not raw_torrents:
                break

            torrents = cast(list[object], cast(object, raw_torrents))
            for raw_torrent in torrents:
                if not isinstance(raw_torrent, dict):
                    continue
                torrent = cast(dict[str, object], cast(object, raw_torrent))
                title = str(torrent.get("title", ""))
                if self._matches_season_episode(title, season, episode):
                    self._print_result(torrent)

            total = data.get("torrents_count", 0)
            if page * 100 >= int(str(total)) or len(torrents) < 100:
                break
            page += 1

    def _search_by_keywords(
        self, keywords: str, season: int | None = None, episode: int | None = None
    ) -> None:
        terms = [t.lower() for t in keywords.split() if t]
        page = 1

        for _ in range(MAX_PAGES):
            api_url = "{}/api/get-torrents?limit=100&page={}&Keywords={}".format(
                self.url, page, keywords.replace(" ", "+")
            )
            try:
                response = retrieve_url(api_url)
                data_value: object = cast(object, json.loads(response))
            except Exception:
                break
            if not isinstance(data_value, dict):
                break
            data = cast(dict[str, object], cast(object, data_value))

            raw_torrents = data.get("torrents", [])
            if not isinstance(raw_torrents, list) or not raw_torrents:
                break

            torrents = cast(list[object], cast(object, raw_torrents))
            for raw_torrent in torrents:
                if not isinstance(raw_torrent, dict):
                    continue
                torrent = cast(dict[str, object], cast(object, raw_torrent))
                title = str(torrent.get("title", ""))
                title_lower = title.lower()
                if all(term in title_lower for term in terms) and self._matches_season_episode(
                    title, season, episode
                ):
                    self._print_result(torrent)

            total = data.get("torrents_count", 0)
            if page * 100 >= int(str(total)) or len(torrents) < 100:
                break
            page += 1

    def _print_result(self, torrent: dict[str, object]) -> None:
        link = str(torrent.get("magnet_url") or torrent.get("torrent_url", ""))
        if not link:
            return
        result = SearchResults(
            link=link,
            name=str(torrent.get("title", "Unknown")),
            size=self._format_size(cast(Union[int, str], torrent.get("size_bytes", -1))),
            seeds=int(str(torrent.get("seeds", 0))),
            leech=int(str(torrent.get("peers", 0))),
            engine_url=self.url,
            desc_link=str(torrent.get("episode_url", self.url)),
        )
        try:
            result["pub_date"] = int(str(torrent["date_released_unix"]))
        except (KeyError, TypeError, ValueError):
            pass
        _qbt_prettyPrinter(result)

    def _format_size(self, size_bytes: int | str) -> str:
        try:
            size_bytes = int(size_bytes)
        except (TypeError, ValueError):
            return "-1"
        if size_bytes < 0:
            return "-1"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.1f} MB"
        else:
            return f"{size_bytes / (1024**3):.2f} GB"
