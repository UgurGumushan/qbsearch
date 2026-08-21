# VERSION: 1.9
"""
YTS (https://yts.bz) search engine. Queries the YTS JSON API; quality, codec,
rating and genre tags embedded in the search text (e.g. "movie 1080p x265")
are parsed out of the query and sent as API parameters instead.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Callable, ClassVar, TypeVar
from urllib.parse import unquote, urlencode

from helpers import retrieve_url as _qbt_helper_retrieve_url  # noqa: F401
from novaprinter import SearchResults, prettyPrinter

# BEGIN GENERATED QBITT SAFETY PREAMBLE
# This block is rendered into each standalone engine.  Keep it stdlib-only.
try:
    import socket as _qbt_socket
    import time as _qbt_time
    import urllib.error as _qbt_urllib_error
    from concurrent.futures import ThreadPoolExecutor as _QBTThreadPoolExecutor
    from concurrent.futures import TimeoutError as _qbt_FuturesTimeoutError
    from concurrent.futures import as_completed as _qbt_as_completed
    from threading import Lock as _qbt_Lock
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
_qbt_search_deadline = None


class _QBTEmptyResponse:
    """Response-shaped empty value used when a request is exhausted."""

    status = 200
    code = 200

    def __init__(self, url: object = "") -> None:
        self._url = str(getattr(url, "full_url", url))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False

    def close(self) -> None:
        return None

    def read(self, *args, **kwargs) -> bytes:
        return b""

    def getcode(self) -> int:
        return self.code

    def geturl(self) -> str:
        return self._url

    def getheader(self, name: str, default: object = None):
        return default

    def info(self):
        return self

    def get(self, name: str, default: object = None):
        return default


class _QBTTransientHTTPError(Exception):
    pass


def _qbt_sleep(attempt: int) -> None:
    _qbt_time.sleep(min(max(RETRY_DELAY, 0.0) * (attempt + 1), 1.0))


def _qbt_retry_call(operation) -> str:
    """Run a helper request a bounded number of times and return empty data."""
    for attempt in range(max(1, int(MAX_ATTEMPTS))):
        if _qbt_time.monotonic() >= _qbt_get_deadline():
            return ""
        try:
            result = operation()
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


def _qbt_safe_urlopen(url, data=None, *, context=None):
    """Open a URL with explicit timeout/retry policy and an empty fallback."""
    attempts = max(1, int(MAX_ATTEMPTS))
    for attempt in range(attempts):
        remaining = _qbt_get_deadline() - _qbt_time.monotonic()
        if remaining <= 0:
            return _QBTEmptyResponse(url)
        response = None
        try:
            request_timeout = min(float(HTTP_TIMEOUT), remaining)
            if context is None:
                response = _qbt_urlopen(url, data=data, timeout=request_timeout)
            else:
                response = _qbt_urlopen(
                    url, data=data, timeout=request_timeout, context=context
                )
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if status in _QBT_RETRYABLE_HTTP_STATUS:
                response.close()
                response = None
                raise _QBTTransientHTTPError(status)
            if status is not None and status >= 400:
                response.close()
                return _QBTEmptyResponse(url)
            return response
        except _qbt_urllib_error.HTTPError as error:
            if error.code not in _QBT_RETRYABLE_HTTP_STATUS:
                try:
                    error.close()
                except Exception:
                    pass
                return _QBTEmptyResponse(url)
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
            return _QBTEmptyResponse(url)
        if attempt + 1 < attempts:
            _qbt_sleep(attempt)
    return _QBTEmptyResponse(url)


_qbt_retrieve_url = globals().get("_qbt_helper_retrieve_url")


def retrieve_url(*args, **kwargs) -> str:
    """Drop-in wrapper for qBittorrent's helper with bounded retries."""
    helper = _qbt_retrieve_url
    if not callable(helper):
        return ""
    return _qbt_retry_call(lambda: helper(*args, **kwargs))


_qbt_output_lock = _qbt_Lock()


def _qbt_prettyPrinter(result) -> None:
    """Serialize result records emitted by parallel workers."""
    with _qbt_output_lock:
        prettyPrinter(result)


def _qbt_run_parallel(worker, jobs, deadline=None):
    """Run bounded worker jobs, preserving completed work after failures."""
    jobs = list(jobs)
    if not jobs:
        return []
    if deadline is None:
        deadline = _qbt_get_deadline()
    executor = _QBTThreadPoolExecutor(max_workers=MAX_WORKERS)
    futures = []
    for job in jobs:
        if isinstance(job, tuple):
            futures.append(executor.submit(worker, *job))
        else:
            futures.append(executor.submit(worker, job))
    results = []
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
            future.cancel()
    finally:
        try:
            executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:  # pragma: no cover - compatibility with old qBitt Python
            executor.shutdown(wait=False)
    return results


def _qbt_new_deadline() -> float:
    return _qbt_get_deadline()


def _qbt_get_deadline() -> float:
    global _qbt_search_deadline
    if _qbt_search_deadline is None:
        _qbt_search_deadline = _qbt_time.monotonic() + max(0.0, float(SEARCH_DEADLINE))
    return _qbt_search_deadline


# END GENERATED QBITT SAFETY PREAMBLE


# https://stackoverflow.com/a/78110564
_Cls = TypeVar("_Cls", bound=type)


def filter_unexpected_fields(cls: _Cls) -> _Cls:
    original_init: Callable[..., None] = cls.__init__

    def new_init(self: object, *args: object, **kwargs: object) -> None:
        expected_fields = {field.name for field in dataclasses.fields(cls)}
        cleaned_kwargs = {key: value for key, value in kwargs.items() if key in expected_fields}
        original_init(self, *args, **cleaned_kwargs)

    cls.__init__ = new_init
    return cls


@filter_unexpected_fields
@dataclasses.dataclass
class yts_torrent:
    url: str
    seeds: int
    peers: int
    size_bytes: int
    hash: str | None = None
    size: str | None = None
    quality: str | None = None
    type: str | None = None
    is_repack: str | None = None
    video_codec: str | None = None
    date_uploaded: str | None = None
    date_uploaded_unix: int | None = None
    bit_depth: str | None = None
    audio_channels: str | None = None


@filter_unexpected_fields
@dataclasses.dataclass
class yts_movie:
    id: int
    url: str
    title: str
    title_long: str | None = None
    slug: str | None = None
    year: int | None = None
    genres: list[str] | None = None
    language: str | None = None
    torrents: list[yts_torrent] | None = None
    date_uploaded: str | None = None
    date_uploaded_unix: int | None = None

    def __post_init__(self):
        self.torrents = self.torrents and [yts_torrent(**torrent) for torrent in self.torrents]  # pyright: ignore[reportCallIssue]


@filter_unexpected_fields
@dataclasses.dataclass
class yts_data:
    movie_count: int
    limit: int
    page_number: int
    movies: list[yts_movie] | None = None

    def __post_init__(self):
        self.movies = self.movies and [yts_movie(**movie) for movie in self.movies]  # pyright: ignore[reportCallIssue]


@filter_unexpected_fields
@dataclasses.dataclass
class yts_response:
    status: str
    status_message: str
    data: yts_data

    def __post_init__(self):
        self.data = yts_data(**self.data)  # pyright: ignore[reportCallIssue]


class yts:
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their corresponding id,
    possible categories are ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv').
    """

    url = "https://yts.bz/"
    api_url = "https://movies-api.accel.li/api/v2/list_movies.json?"
    name = "YTS"
    supported_categories: ClassVar[dict[str, str]] = {"all": "0", "movies": "1"}

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what: str, cat: str = "all"):
        """
        Searches YTS' API for `what`.

        Automatically parses rating, codec, and quality from `what`.

        @param `what`: a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        @param `cat`: the name of a search category in ('all', 'anime', 'books', 'games', 'movies', 'music', 'pictures', 'software', 'tv')
        """
        search_url = self.api_url

        what = unquote(what)
        search_params: dict[str, str] = {}

        # quality tagging
        quality_rstring = r"(?:quality=)?((?:2160|1440|1080|720|480|240)p|3D)"
        quality_re = re.search(quality_rstring, what)
        search_resolution = None
        if quality_re:
            search_resolution = quality_re.group(1)
            search_params["quality"] = search_resolution
            what = re.sub(quality_rstring, "", what).strip()

        # codec tagging
        # YTS only provides h264/h265 at time of writing
        codec_rstring = r"(?:x|h)(264|265)"
        codec_re = re.search(codec_rstring, what)
        search_codec = None
        if codec_re:
            search_codec = "x" + codec_re.group(1)
            # only add if quality also defined, will be checked separately anyways
            if "quality" in search_params:
                search_params["quality"] += f".{search_codec}"
            what = re.sub(codec_rstring, "", what).strip()

        # rating tagging
        rating_rstring = r"(?:min(?:imum)?_)?rating=(\d)"
        rating_re = re.search(rating_rstring, what)
        if rating_re:
            min_rating = rating_re.group(1)
            search_params["minimum_rating"] = min_rating
            what = re.sub(rating_rstring, "", what).strip()

        # genre tagging
        genre_rstring = r"genre=(\w+)"
        genre_re = re.search(genre_rstring, what)
        if genre_re:
            genre = genre_re.group(1)
            what = re.sub(genre_rstring, "", what).strip()
            search_params["genre"] = genre

        # prevent user causing page errors
        search_rstring = r"&page=\d+"
        what = re.sub(search_rstring, "", what).strip()

        # url finalisation
        if what:
            search_params["query_term"] = what

        search_url += urlencode(search_params)

        try:
            response_raw = retrieve_url(search_url)
            response_json = json.loads(response_raw)
            api_result = yts_response(**response_json)
        except Exception as e:
            print(f"Error parsing YTS response: {e}")
            return

        if api_result.status != "ok":
            print(f"Error querying YTS API: {api_result.status}: {api_result.status_message}")
            return
        if not api_result.data or not api_result.data.movies:
            return

        self.process_movies(api_result.data.movies or [], search_params)
        for page_no in range(
            1, min(api_result.data.movie_count // api_result.data.limit + 1, MAX_PAGES + 1)
        ):
            try:
                api_result = yts_response(
                    **json.loads(retrieve_url(search_url + f"&page={page_no}"))
                )
                self.process_movies(api_result.data.movies or [], search_params)
            except Exception as e:
                print(f"Error parsing YTS response: {e}")
                return

    def process_movies(self, movies: list[yts_movie] | None, search_params: dict[str, str]) -> None:
        for movie in movies or []:
            for torrent in movie.torrents or []:
                if (
                    "search_codec" in search_params
                    and torrent.video_codec != search_params["search_codec"]
                ) or (
                    "search_resolution" in search_params
                    and torrent.quality != search_params["search_resolution"]
                ):
                    continue
                formatTorrent: SearchResults = {
                    "link": torrent.url,
                    "name": f"{movie.title_long or movie.title} {torrent.quality and f'[{torrent.quality}]'} {torrent.video_codec and f'[{torrent.video_codec}]'} {torrent.type and f'[{torrent.type}]'} {torrent.audio_channels and f'[{torrent.audio_channels}]'} [YTS]",
                    "size": torrent.size if torrent.size is not None else -1,
                    "seeds": torrent.seeds,
                    "leech": torrent.peers,
                    "engine_url": self.url,
                    "desc_link": movie.url,
                }
                if torrent.date_uploaded_unix is not None:
                    formatTorrent["pub_date"] = torrent.date_uploaded_unix
                _qbt_prettyPrinter(formatTorrent)
