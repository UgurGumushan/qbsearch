# VERSION: 1.3
"""
The RARBG (https://therarbg.com) search engine. Uses the site's JSON search
endpoint and builds magnets directly from the hash returned for each result.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import quote

from helpers import download_file
from helpers import retrieve_url as _qbt_helper_retrieve_url
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


_qbt_retrieve_url = _qbt_helper_retrieve_url


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


class therarbg:
    url = "https://therarbg.com"
    name = "The RarBg"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "All",
        "movies": "Movies",
        "tv": "TV",
        "music": "Music",
        "games": "Games",
        "anime": "Anime",
        "software": "Apps",
    }

    next_page_regex = r"<a.*?>»<\/a>"
    title_regex = r"<title>Search for.*<\/title>"
    has_next_page = True

    class MyHtmlParser(HTMLParser):
        def error(self, message: str) -> None:
            pass

        DIV, TABLE, TBODY, TR, TD, A, SPAN, I, B = (
            "div",
            "table",
            "tbody",
            "tr",
            "td",
            "a",
            "span",
            "i",
            "b",
        )

        def __init__(self, url: str) -> None:
            HTMLParser.__init__(self)
            self.magnet_regex = r'href=["\']magnet:.+?["\']'

            self.url = url
            self.row: dict[str, str] = {}
            self.column = 0

            self.foundTable = False
            self.foundTableTbody = False
            self.insideRow = False
            self.insideCell = False

            self.shouldParseName = False
            self.shouldGetCategory = False
            self.shouldGetSize = False
            self.shouldGetSeeds = False
            self.shouldGetLeechs = False

            self.alreadyParseName = False
            self.alreadyParsesLink = False

        def handle_starttag(self, tag: str, attrs: Sequence[tuple[str, str | None]]) -> None:
            params = dict(attrs)

            if tag == self.TABLE:
                self.foundTable = True

            if tag == self.TBODY and self.foundTable:
                self.foundTableTbody = True

            if tag == self.TR and self.foundTableTbody:
                self.column = 0
                self.insideRow = True

            if tag == self.TD and self.insideRow:
                self.column += 1
                self.insideCell = True

            if self.insideCell:
                if self.column == 2 and tag == self.A and not self.alreadyParseName:
                    self.shouldParseName = True
                    href = params.get("href")
                    link = f"{self.url}/{href}"
                    self.row["desc_link"] = link

                    torrent_page = retrieve_url(link)
                    matches = re.finditer(self.magnet_regex, torrent_page, re.MULTILINE)
                    magnet_urls = [x.group() for x in matches]
                    self.row["link"] = magnet_urls[0].split('"')[1]

                if self.column == 3 and tag == self.A:
                    self.shouldGetCategory = True

                if self.column == 6:
                    self.shouldGetSize = True

                if self.column == 7:
                    self.shouldGetSeeds = True

                if self.column == 8:
                    self.shouldGetLeechs = True

        def handle_data(self, data: str) -> None:
            if self.shouldParseName:
                self.row["name"] = data
                self.shouldParseName = False
                self.alreadyParseName = True

            if self.shouldGetCategory:
                self.row["name"] += f" ({data.strip()})"
                self.shouldGetCategory = False

            if self.shouldGetSize:
                self.row["size"] = data.replace(",", ".").replace("\xa0", " ")
                self.shouldGetSize = False

            if self.shouldGetSeeds:
                self.row["seeds"] = data
                self.shouldGetSeeds = False

            if self.shouldGetLeechs:
                self.row["leech"] = data
                self.shouldGetLeechs = False

        def handle_endtag(self, tag: str) -> None:
            if tag == self.TD:
                self.insideCell = False

            if tag == self.TR and self.foundTableTbody:
                data = SearchResults(
                    link=self.row.get("link", "-1"),
                    name=self.row.get("name", "-1"),
                    size=self.row.get("size", "-1"),
                    seeds=int(self.row.get("seeds", "-1")),
                    leech=int(self.row.get("leech", "-1")),
                    engine_url=self.url,
                    desc_link=self.row.get("desc_link", "-1"),
                )
                _qbt_prettyPrinter(data)
                self.column = 0
                self.row = {}
                self.insideRow = False
                self.alreadyParseName = False

    def download_torrent(self, info: str) -> None:
        print(download_file(info))

    def getPageUrl(self, what: str, cat: str, page: int) -> str:
        category = "" if cat == "All" else f":category:{quote(cat, safe='')}"
        return (
            f"{self.url}/get-posts/keywords:{quote(what, safe='%+')}{category}"
            f":format:json/?page={page}"
        )

    @staticmethod
    def _int_value(value: object, default: int = -1) -> int:
        if not isinstance(value, (int, str, float)):
            return default
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _result_from_json(self, post: dict[object, object]) -> SearchResults | None:
        name = str(post.get("n") or "").strip()
        info_hash = str(post.get("h") or "").strip()
        if not name or not info_hash:
            return None

        post_id = str(post.get("pk") or "").strip()
        slug = quote(re.sub(r"[ .]+", "-", name).lower(), safe="-_")
        desc_link = (
            f"{self.url}/post-detail/{post_id}/{slug}/"
            if post_id
            else self.url
        )
        result: SearchResults = {
            "link": (
                f"magnet:?xt=urn:btih:{quote(info_hash, safe='')}"
                f"&dn={quote(name, safe='')}"
            ),
            "name": name,
            "size": f"{self._int_value(post.get('s'), 0)} B",
            "seeds": self._int_value(post.get("se")),
            "leech": self._int_value(post.get("le")),
            "engine_url": self.url,
            "desc_link": desc_link,
        }
        added = self._int_value(post.get("a"), -1)
        if added >= 0:
            result["pub_date"] = added
        return result

    def search(self, what: str, cat: str = "all") -> None:
        search_category = self.supported_categories[cat]
        page_url = self.getPageUrl(what, search_category, 1)
        for _ in range(MAX_PAGES):
            response = retrieve_url(page_url)
            try:
                payload = json.loads(response)
            except (TypeError, ValueError):
                return
            if not isinstance(payload, dict):
                return

            posts = payload.get("results")
            if not isinstance(posts, list):
                return
            for post in posts:
                if not isinstance(post, dict):
                    continue
                result = self._result_from_json(post)
                if result is not None:
                    _qbt_prettyPrinter(result)

            links = payload.get("links")
            next_url = links.get("next") if isinstance(links, dict) else None
            if not isinstance(next_url, str) or not next_url:
                return
            page_url = next_url
