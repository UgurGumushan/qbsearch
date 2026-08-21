# VERSION: 1.00
"""
RedeTorrent (redetorrent.com, content with Portuguese audio: dubbed, dual
audio, subtitled) movies, series and anime search. Scrapes the paginated
result cards, then each item's detail page for the magnets under its
download list.
"""

# https://redetorrent.com
from __future__ import annotations

import html
import re
import sys
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import ClassVar
from urllib.parse import quote_plus, unquote, urljoin

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


class redetorrent:
    url = "https://redetorrent.com"
    name = "RedeTorrent"
    supported_categories: ClassVar[dict[str, str]] = {
        "all": "all",
        "anime": "desenhos",
        "movies": "filmes",
        "tv": "series",
    }

    class SearchResultsParser(HTMLParser):
        def __init__(self, base_url: str) -> None:
            HTMLParser.__init__(self)
            self.base_url = base_url
            self.results: list[dict[str, str]] = []

            self.inside_card = False
            self.div_depth = 0
            self.inside_headline = False
            self.current_link = ""
            self.current_title = ""

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == "div":
                if "capa_lista" in self._get(params, "class"):
                    self.inside_card = True
                    self.div_depth = 1
                    self.current_link = ""
                    self.current_title = ""
                elif self.inside_card:
                    self.div_depth += 1
                return

            if not self.inside_card:
                return

            if tag == "a":
                href = self._get(params, "href")
                if href and not self.current_link:
                    self.current_link = urljoin(self.base_url, href)

            if tag == "h2" and self._get(params, "itemprop") == "headline":
                self.inside_headline = True

        def handle_data(self, data: str) -> None:
            if self.inside_card and self.inside_headline:
                text = self._clean_text(data)

                if text:
                    if self.current_title:
                        self.current_title += " "
                    self.current_title += text

        def handle_endtag(self, tag: str) -> None:
            if tag == "h2" and self.inside_headline:
                self.inside_headline = False

            if tag == "div" and self.inside_card:
                self.div_depth -= 1
                if self.div_depth <= 0:
                    title = self._clean_title(self.current_title)

                    if self.current_link and title:
                        self.results.append(
                            {
                                "title": title,
                                "desc_link": self.current_link,
                            }
                        )

                    self.inside_card = False
                    self.div_depth = 0
                    self.current_link = ""
                    self.current_title = ""

        def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ""

            return result

        def _get(self, params: Mapping[str, str], key: str) -> str:
            return params.get(key, "")

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r"\s*Download\s*$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+", " ", title)
            return title.strip()

    class MagnetLinksParser(HTMLParser):
        def __init__(self) -> None:
            HTMLParser.__init__(self)
            self.magnets: list[dict[str, str]] = []
            self.inside_download_area = False

        def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
            params = self._attrs_to_dict(attrs)

            if tag == "p" and params.get("id") == "lista_download":
                self.inside_download_area = True
                return

            if not self.inside_download_area:
                return

            if tag == "a":
                href = params.get("href", "")
                title = params.get("title", "")

                if href.startswith("magnet:?"):
                    self.magnets.append(
                        {
                            "magnet": html.unescape(href),
                            "title": self._clean_title(title),
                        }
                    )

        def handle_endtag(self, tag: str) -> None:
            if tag == "p" and self.inside_download_area:
                self.inside_download_area = False

        def _attrs_to_dict(self, attrs: list[tuple[str, str | None]]) -> dict[str, str]:
            result = {}

            for key, value in attrs:
                result[key] = value if value is not None else ""

            return result

        def _clean_text(self, text: str) -> str:
            text = html.unescape(text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

        def _clean_title(self, title: str) -> str:
            title = self._clean_text(title)
            title = re.sub(r"^DOWNLOAD\s+", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+", " ", title)
            return title.strip()

    def search(self, what: str, cat: str = "all") -> None:
        search_url = self._build_search_url(what, cat)

        try:
            search_html = retrieve_url(search_url)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Rede Torrent search request failed: {exc}", file=sys.stderr)
            return

        search_parser = self.SearchResultsParser(self.url)
        search_parser.feed(search_html)
        search_parser.close()

        for result in search_parser.results:
            self._print_result_magnets(result)

    def _build_search_url(self, what: str, cat: str) -> str:
        query = what.replace("%20", "+")

        if cat not in self.supported_categories:
            cat = "all"

        return self.url + "/index.php?s=" + quote_plus(query).replace("%2B", "+")

    def _print_result_magnets(self, result: dict[str, str]) -> None:
        desc_link = result.get("desc_link", "")
        base_title = result.get("title", "").strip()

        if not desc_link:
            return

        try:
            details_html = retrieve_url(desc_link)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            print(f"Rede Torrent details request failed: {exc}", file=sys.stderr)
            return

        magnet_parser = self.MagnetLinksParser()
        magnet_parser.feed(details_html)
        magnet_parser.close()

        for magnet_item in magnet_parser.magnets:
            magnet = magnet_item.get("magnet", "")
            magnet_title = magnet_item.get("title", "")

            if not magnet:
                continue

            name = self._build_result_name(base_title, magnet_title, magnet)

            torrent_info = SearchResults(
                link=magnet,
                name=name,
                size="-1",
                seeds=-1,
                leech=-1,
                engine_url=self.url,
                desc_link=desc_link,
                pub_date=-1,
            )

            _qbt_prettyPrinter(torrent_info)

    def _build_result_name(self, base_title: str, magnet_title: str, magnet: str) -> str:
        if magnet_title:
            return base_title + " - " + magnet_title

        magnet_name = self._extract_magnet_dn(magnet)

        if magnet_name:
            return base_title + " - " + magnet_name

        return base_title

    def _extract_magnet_dn(self, magnet: str) -> str:
        match = re.search(r"[?&]dn=([^&]+)", magnet)

        if not match:
            return ""

        name = unquote(match.group(1))
        name = name.replace(".", " ")
        name = re.sub(r"\s+", " ", name)

        return name.strip()
